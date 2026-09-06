import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import type {
  AcknowledgeProductionHandoverSlotCommand,
  HandoverPackageView,
  ObservationPeriodRevision,
  ProductionTransitionDataSource,
  ProductionTransitionExternalUnavailableProvider,
  ProductionTransitionSourceKind,
  ProductionTransitionWorkspace,
} from "../api/production-transition-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { DockedInspector } from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import type { SemanticTone } from "../domain/view-models";
import { formatDate, formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, focusControl } from "../ui-adapters/npi-ui";

const unresolvedPageSize = 25;
const maximumUnresolvedActions = 10_000;

type WorkspaceView = "handover" | "observation";

type ResourceState =
  | { kind: "loading" }
  | { kind: "loaded"; value: ProductionTransitionWorkspace }
  | { kind: "failed"; failure: RequestFailure };

interface RetryableAcknowledgement {
  readonly command: AcknowledgeProductionHandoverSlotCommand;
  readonly handoverId: string;
  readonly handoverVersion: number;
  readonly idempotencyKey: string;
}

type FrozenAcknowledgementSlot =
  HandoverPackageView["revision"]["slots"][number];

interface AcknowledgementEligibility {
  readonly candidates: readonly FrozenAcknowledgementSlot[];
  readonly hold: string | null;
}

type CommandState =
  | { kind: "idle" }
  | { kind: "processing" }
  | {
      kind: "succeeded";
      replayed: boolean;
      refreshFailure: RequestFailure | null;
    }
  | { kind: "failed"; failure: RequestFailure };

type InspectorSelection =
  | { kind: "slot"; key: string }
  | { kind: "manifest"; key: string }
  | { kind: "unresolved"; key: string }
  | { kind: "provider"; key: string }
  | { kind: "observation-reference"; key: string };

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    failure.problem?.retryable === true ||
    failure.problem?.status === 409
  );
}

function canRetrySameCommand(failure: RequestFailure): boolean {
  return failure.problem?.status !== 409 && canRetry(failure);
}

function sourceKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: ProductionTransitionSourceKind,
): string {
  switch (kind) {
    case "readiness_instance_revision":
      return t("Readiness instance revision");
    case "domain_work_item":
      return t("Project work item");
    case "released_document":
      return t("Released document");
    case "release_baseline":
      return t("Release baseline");
    case "file_revision":
      return t("File revision");
    case "tooling_capacity_scenario":
      return t("Tooling capacity scenario");
    case "trial_defect_revision":
      return t("Trial defect revision");
    case "trial_review_reference":
      return t("Trial review reference");
    case "trial_conclusion":
      return t("Trial conclusion");
  }
}

function providerLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: ProductionTransitionExternalUnavailableProvider["kind"],
): string {
  switch (kind) {
    case "actual_sop":
      return t("Actual SOP");
    case "first_batch_yield":
      return t("First-batch yield");
    case "customer_complaint":
      return t("Customer complaints");
    case "production_cycle_time":
      return t("Production cycle time");
    case "tooling_stability":
      return t("Tooling stability");
  }
}

function providerReason(
  t: ReturnType<typeof useI18n>["t"],
  provider: ProductionTransitionExternalUnavailableProvider,
): string {
  switch (provider.reasonCode) {
    case "actual_sop_provider_unavailable":
      return t("The actual SOP provider is unavailable.");
    case "first_batch_yield_provider_unavailable":
      return t("The first-batch yield provider is unavailable.");
    case "customer_complaint_provider_unavailable":
      return t("The customer complaint provider is unavailable.");
    case "production_cycle_time_provider_unavailable":
      return t("The production cycle time provider is unavailable.");
    case "tooling_stability_provider_unavailable":
      return t("The Tooling stability provider is unavailable.");
  }
}

function directionLabel(
  t: ReturnType<typeof useI18n>["t"],
  direction: "sender" | "receiver",
): string {
  return direction === "sender" ? t("Sender") : t("Receiver");
}

function workKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: HandoverPackageView["revision"]["unresolvedActions"][number]["kind"],
): string {
  switch (kind) {
    case "action":
      return t("Action");
    case "decision_request":
      return t("Decision request");
    case "issue":
      return t("Issue");
    case "risk":
      return t("Risk");
  }
}

function workStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: string,
): string {
  switch (state) {
    case "open":
      return t("Open");
    case "assigned":
      return t("Assigned");
    case "in_progress":
      return t("In progress");
    case "ready_for_verification":
      return t("Ready for verification");
    case "closed":
      return t("Closed");
    case "reopened":
      return t("Reopened");
    default:
      return t("Unrecognized state");
  }
}

function LoadingState(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section
      aria-busy="true"
      aria-label={t("Loading production transition")}
      className="workspace-resource-state workspace-resource-state--loading"
      data-testid="production-transition-loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">
        {t("Loading production transition")}
      </span>
    </section>
  );
}

function FailureState({
  failure,
  onRetry,
}: {
  failure: RequestFailure;
  onRetry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const denied =
    failure.problem?.status === 401 || failure.problem?.status === 403;
  const conflict = failure.problem?.status === 409;
  return (
    <section
      className="workspace-resource-state"
      data-testid="production-transition-error"
      role="alert"
    >
      <SemanticStatus
        label={
          denied ? t("No permission") : conflict ? t("Conflict") : t("Error")
        }
        tone={conflict ? "warning" : "danger"}
      />
      <h2>
        {denied
          ? t("Production transition access is not available")
          : conflict
            ? t("The production transition workspace is out of date")
            : t("Production transition data is unavailable")}
      </h2>
      <p>
        {denied
          ? t("No protected production transition data was displayed.")
          : conflict
            ? t("Reload the exact current package before continuing.")
            : t("Use the reference ID for support or retry when available.")}
      </p>
      <RequestFailurePanel failure={failure} />
      {canRetry(failure) ? (
        <Button icon="refresh" onClick={onRetry}>
          {conflict ? t("Reload current data") : t("Retry")}
        </Button>
      ) : null}
    </section>
  );
}

function historyTone(
  current: boolean,
  fullyAcknowledged: boolean,
): SemanticTone {
  if (!current) return "neutral";
  return fullyAcknowledged ? "success" : "warning";
}

function HandoverHistory({
  currentRevisionId,
  history,
  navigationLocked,
  onSelect,
  selectedRevisionId,
}: {
  currentRevisionId: string | null;
  history: readonly HandoverPackageView[];
  navigationLocked: boolean;
  onSelect: (value: HandoverPackageView) => void;
  selectedRevisionId: string | null;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  return (
    <Panel
      bodyClassName="production-transition-workspace__history-body"
      className="production-transition-workspace__history"
      scrollableBody
      title={t("Handover history")}
    >
      {history.length ? (
        <ol data-testid="handover-history">
          {[...history].reverse().map((entry) => {
            const current = entry.revision.globalId === currentRevisionId;
            return (
              <li key={entry.revision.globalId}>
                <button
                  aria-current={
                    selectedRevisionId === entry.revision.globalId
                      ? "page"
                      : undefined
                  }
                  className="production-transition-workspace__history-select"
                  data-testid={`handover-history-${String(entry.revision.handoverVersion)}`}
                  disabled={navigationLocked}
                  onClick={() => {
                    onSelect(entry);
                  }}
                  type="button"
                >
                  <strong>
                    {t("Package revision {{version}}", {
                      version: entry.revision.handoverVersion,
                    })}
                  </strong>
                  <time dateTime={entry.revision.createdAt}>
                    {formatDateTime(locale, entry.revision.createdAt)}
                  </time>
                  <SemanticStatus
                    label={
                      current ? t("Current package") : t("Superseded package")
                    }
                    tone={historyTone(current, entry.fullyAcknowledged)}
                  />
                </button>
              </li>
            );
          })}
        </ol>
      ) : (
        <p>{t("No handover package has been retained.")}</p>
      )}
    </Panel>
  );
}

function ObservationHistory({
  currentRevisionId,
  history,
  onSelect,
  selectedRevisionId,
}: {
  currentRevisionId: string | null;
  history: readonly ObservationPeriodRevision[];
  onSelect: (value: ObservationPeriodRevision) => void;
  selectedRevisionId: string | null;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  return (
    <Panel
      bodyClassName="production-transition-workspace__history-body"
      className="production-transition-workspace__history"
      scrollableBody
      title={t("Observation history")}
    >
      {history.length ? (
        <ol data-testid="observation-history">
          {[...history].reverse().map((revision) => {
            const current = revision.globalId === currentRevisionId;
            return (
              <li key={revision.globalId}>
                <button
                  aria-current={
                    selectedRevisionId === revision.globalId
                      ? "page"
                      : undefined
                  }
                  className="production-transition-workspace__history-select"
                  data-testid={`observation-history-${String(revision.observationVersion)}`}
                  onClick={() => {
                    onSelect(revision);
                  }}
                  type="button"
                >
                  <strong>
                    {t("Observation revision {{version}}", {
                      version: revision.observationVersion,
                    })}
                  </strong>
                  <time dateTime={revision.createdAt}>
                    {formatDateTime(locale, revision.createdAt)}
                  </time>
                  <SemanticStatus
                    label={current ? t("Current revision") : t("Superseded")}
                    tone={current ? "warning" : "neutral"}
                  />
                </button>
              </li>
            );
          })}
        </ol>
      ) : (
        <p>{t("No observation revision has been retained.")}</p>
      )}
    </Panel>
  );
}

function Pagination({
  currentPage,
  itemCount,
  onPageChange,
}: {
  currentPage: number;
  itemCount: number;
  onPageChange: (page: number) => void;
}): React.JSX.Element | null {
  const { t } = useI18n();
  const pages = Math.max(1, Math.ceil(itemCount / unresolvedPageSize));
  if (pages <= 1) return null;
  return (
    <nav
      aria-label={t("Unresolved action pages")}
      className="production-transition-workspace__pagination"
    >
      <Button
        disabled={currentPage <= 0}
        onClick={() => {
          onPageChange(currentPage - 1);
        }}
        visual="ghost"
      >
        {t("Previous page")}
      </Button>
      <span aria-live="polite">
        {t("Page {{page}} of {{pages}}", {
          page: currentPage + 1,
          pages,
        })}
      </span>
      <Button
        disabled={currentPage + 1 >= pages}
        onClick={() => {
          onPageChange(currentPage + 1);
        }}
        visual="ghost"
      >
        {t("Next page")}
      </Button>
    </nav>
  );
}

function CommandFeedback({
  onReload,
  onRetry,
  state,
}: {
  onReload: () => void;
  onRetry: () => void;
  state: CommandState;
}): React.JSX.Element | null {
  const { t } = useI18n();
  if (state.kind === "idle") return null;
  if (state.kind === "processing") {
    return (
      <div
        aria-live="polite"
        className="production-transition-workspace__command-state"
        data-testid="acknowledgement-processing"
        role="status"
      >
        <SemanticStatus label={t("Processing")} tone="info" />
        <p>
          {t(
            "The exact acknowledgement is being appended. Do not submit it again.",
          )}
        </p>
      </div>
    );
  }
  if (state.kind === "succeeded") {
    if (state.refreshFailure) {
      return (
        <div
          className="production-transition-workspace__command-state"
          data-testid="acknowledgement-refresh-failed"
          role="alert"
        >
          <SemanticStatus label={t("Refresh failed")} tone="warning" />
          <p>
            {t(
              "The acknowledgement response was accepted, but current data could not be refreshed. Reload before making another decision.",
            )}
          </p>
          <RequestFailurePanel failure={state.refreshFailure} />
          <Button icon="refresh" onClick={onReload}>
            {t("Reload current data")}
          </Button>
        </div>
      );
    }
    return (
      <div
        aria-live="polite"
        className="production-transition-workspace__command-state"
        data-testid="acknowledgement-succeeded"
        role="status"
      >
        <SemanticStatus label={t("Acknowledgement retained")} tone="success" />
        <p>
          {state.replayed
            ? t("The original acknowledgement result was replayed safely.")
            : t("The immutable acknowledgement fact is now retained.")}
        </p>
      </div>
    );
  }
  const status = state.failure.problem?.status;
  const conflict = status === 409;
  const denied = status === 401 || status === 403;
  const validation = status === 400 || status === 422;
  return (
    <div
      className="production-transition-workspace__command-state"
      data-testid="acknowledgement-failed"
      role="alert"
    >
      <SemanticStatus
        label={
          conflict
            ? t("Conflict")
            : denied
              ? t("No permission")
              : validation
                ? t("Validation error")
                : t("Command failed")
        }
        tone={conflict ? "warning" : "danger"}
      />
      <RequestFailurePanel failure={state.failure} />
      {canRetrySameCommand(state.failure) ? (
        <Button icon="refresh" onClick={onRetry}>
          {t("Retry exact acknowledgement")}
        </Button>
      ) : conflict ? (
        <Button icon="refresh" onClick={onReload}>
          {t("Reload current package")}
        </Button>
      ) : (
        <Button icon="refresh" onClick={onReload}>
          {t("Reload current data")}
        </Button>
      )}
    </div>
  );
}

function HandoverInspector({
  candidate,
  commandState,
  eligibleCandidates,
  onPrepareAcknowledgement,
  onReload,
  onRetry,
  onSelectCandidate,
  permissionHold,
  selection,
  selectionLocked,
  superseded,
  view,
}: {
  candidate: FrozenAcknowledgementSlot | null;
  commandState: CommandState;
  eligibleCandidates: readonly FrozenAcknowledgementSlot[];
  onPrepareAcknowledgement: () => void;
  onReload: () => void;
  onRetry: () => void;
  onSelectCandidate: (slotKey: string | null) => void;
  permissionHold: string | null;
  selection: InspectorSelection | null;
  selectionLocked: boolean;
  superseded: boolean;
  view: HandoverPackageView;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const revision = view.revision;
  const acknowledgementBySlot = new Map(
    view.acknowledgements.map((item) => [item.slotKey, item]),
  );
  const selectedSlot =
    selection?.kind === "slot"
      ? (revision.slots.find((item) => item.slotKey === selection.key) ?? null)
      : null;
  const selectedManifest =
    selection?.kind === "manifest"
      ? (revision.manifest.find(
          (item) =>
            `${item.requirementKey}:${item.kind}:${item.globalId}` ===
            selection.key,
        ) ?? null)
      : null;
  const selectedUnresolved =
    selection?.kind === "unresolved"
      ? (revision.unresolvedActions.find(
          (item) => item.globalId === selection.key,
        ) ?? null)
      : null;
  const acknowledgement = selectedSlot
    ? acknowledgementBySlot.get(selectedSlot.slotKey)
    : undefined;
  const candidateSelectionRequired =
    eligibleCandidates.length > 1 ||
    (eligibleCandidates.length === 1 && !candidate);
  return (
    <DockedInspector
      id="production-transition-inspector"
      title={t("Production transition inspector")}
    >
      <div data-testid="production-transition-inspector">
        {superseded ? (
          <SemanticStatus label={t("Superseded package")} tone="neutral" />
        ) : view.fullyAcknowledged ? (
          <SemanticStatus label={t("Fully acknowledged")} tone="success" />
        ) : (
          <SemanticStatus
            label={t("Acknowledgements pending")}
            tone="warning"
          />
        )}
        <p className="production-transition-workspace__disclaimer">
          {t(
            "Fully acknowledged is a server-derived fact only. It is not a signature, approval, production acceptance, Gate result, G7 closure, or Project completion.",
          )}
        </p>
        {candidateSelectionRequired &&
        (commandState.kind === "idle" || commandState.kind === "processing") ? (
          <div
            className="production-transition-workspace__candidate-selection"
            data-testid="acknowledgement-candidate-selection"
          >
            <label className="field-control">
              <span>{t("Eligible slot")}</span>
              <select
                aria-label={t("Eligible slot")}
                data-testid="acknowledgement-slot-selector"
                disabled={selectionLocked}
                onChange={(event) => {
                  onSelectCandidate(event.currentTarget.value || null);
                }}
                required
                value={candidate?.slotKey ?? ""}
              >
                <option value="">{t("Select")}</option>
                {eligibleCandidates.map((slot) => (
                  <option
                    data-language-exempt="identifier"
                    key={slot.slotKey}
                    value={slot.slotKey}
                  >
                    {slot.slotKey}
                  </option>
                ))}
              </select>
            </label>
            {!candidate ? (
              <div role="status">
                <SemanticStatus label={t("Required")} tone="info" />
                <p>
                  {t("Select one exact eligible slot before acknowledging.")}
                </p>
              </div>
            ) : null}
          </div>
        ) : null}
        {candidate &&
        (commandState.kind === "idle" || commandState.kind === "processing") ? (
          <div className="production-transition-workspace__primary-action">
            <DefinitionList
              rows={[
                {
                  exempt: "identifier",
                  label: t("Eligible slot"),
                  value: candidate.slotKey,
                },
                {
                  exempt: "business-data",
                  label: t("Current actor"),
                  value: candidate.member.userId,
                },
              ]}
            />
            <Button
              data-testid="acknowledge-exact-slot"
              id="acknowledge-exact-slot"
              disabled={commandState.kind === "processing"}
              onClick={onPrepareAcknowledgement}
              visual="primary"
            >
              {t("Acknowledge exact slot")}
            </Button>
          </div>
        ) : commandState.kind === "idle" && eligibleCandidates.length === 0 ? (
          <div
            className="production-transition-workspace__permission-hold"
            data-testid="acknowledgement-unavailable"
            role="status"
          >
            <SemanticStatus label={t("Read only")} tone="info" />
            <p>
              {permissionHold ??
                (sessionCommandContext
                  ? t("No exact current slot is eligible for this actor.")
                  : t(
                      "Session verification is required before an acknowledgement can be prepared.",
                    ))}
            </p>
          </div>
        ) : null}
        <CommandFeedback
          onReload={onReload}
          onRetry={onRetry}
          state={commandState}
        />
        <section className="production-transition-workspace__inspector-detail">
          <h3>{t("Selected exact fact")}</h3>
          {selectedSlot ? (
            <>
              <DefinitionList
                rows={[
                  {
                    exempt: "identifier",
                    label: t("Slot key"),
                    value: selectedSlot.slotKey,
                  },
                  {
                    exempt: "identifier",
                    label: t("Receiving group"),
                    value: selectedSlot.groupKey,
                  },
                  {
                    label: t("Direction"),
                    value: directionLabel(t, selectedSlot.direction),
                  },
                  {
                    exempt: "business-data",
                    label: t("Member"),
                    value: selectedSlot.member.userId,
                  },
                  {
                    exempt: "identifier",
                    label: t("Project role"),
                    value: selectedSlot.role.roleKey,
                  },
                  {
                    label: t("Acknowledgement"),
                    value: acknowledgement ? t("Acknowledged") : t("Pending"),
                  },
                ]}
              />
              {acknowledgement ? (
                <p>
                  <span>{t("Acknowledged at")}: </span>
                  <time dateTime={acknowledgement.acknowledgedAt}>
                    {formatDateTime(locale, acknowledgement.acknowledgedAt)}
                  </time>
                </p>
              ) : null}
            </>
          ) : selectedManifest ? (
            <DefinitionList
              rows={[
                {
                  exempt: "identifier",
                  label: t("Requirement"),
                  value: selectedManifest.requirementKey,
                },
                {
                  label: t("Source kind"),
                  value: sourceKindLabel(t, selectedManifest.kind),
                },
                {
                  exempt: "identifier",
                  label: t("Manifest role"),
                  value: selectedManifest.role,
                },
                {
                  exempt: "identifier",
                  label: t("Source identity"),
                  value: selectedManifest.globalId,
                },
                {
                  label: t("Source version"),
                  value: formatNumber(locale, selectedManifest.sourceVersion),
                },
                {
                  exempt: "identifier",
                  label: t("Snapshot hash"),
                  value: selectedManifest.snapshotHash,
                },
              ]}
            />
          ) : selectedUnresolved ? (
            <DefinitionList
              rows={[
                {
                  label: t("Work item kind"),
                  value: workKindLabel(t, selectedUnresolved.kind),
                },
                {
                  exempt: "identifier",
                  label: t("Work item identity"),
                  value: selectedUnresolved.globalId,
                },
                {
                  label: t("Retained state"),
                  value: workStateLabel(t, selectedUnresolved.state),
                },
                {
                  exempt: "identifier",
                  label: t("Retained state key"),
                  value: selectedUnresolved.state,
                },
                {
                  exempt: "business-data",
                  label: t("Owner"),
                  value: selectedUnresolved.ownerUserId,
                },
                {
                  label: t("Due date"),
                  value: formatDate(locale, selectedUnresolved.dueDate),
                },
                {
                  label: t("Source version"),
                  value: formatNumber(locale, selectedUnresolved.sourceVersion),
                },
              ]}
            />
          ) : (
            <p>{t("Select a retained row to inspect its exact facts.")}</p>
          )}
        </section>
      </div>
    </DockedInspector>
  );
}

function HandoverContent({
  onSelect,
  page,
  selection,
  selectionLocked,
  setPage,
  superseded,
  view,
}: {
  onSelect: (selection: InspectorSelection) => void;
  page: number;
  selection: InspectorSelection | null;
  selectionLocked: boolean;
  setPage: (page: number) => void;
  superseded: boolean;
  view: HandoverPackageView;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const revision = view.revision;
  const acknowledged = new Set(
    view.acknowledgements.map((item) => item.slotKey),
  );
  const boundedUnresolved = revision.unresolvedActions.slice(
    0,
    maximumUnresolvedActions,
  );
  const pages = Math.max(
    1,
    Math.ceil(boundedUnresolved.length / unresolvedPageSize),
  );
  const currentPage = Math.min(page, pages - 1);
  const visibleUnresolved = boundedUnresolved.slice(
    currentPage * unresolvedPageSize,
    (currentPage + 1) * unresolvedPageSize,
  );
  return (
    <div className="production-transition-workspace__content">
      <Panel
        className="production-transition-workspace__summary"
        scrollableBody
        title={t("Handover package")}
      >
        <div className="production-transition-workspace__summary-grid">
          <div>
            <SemanticStatus
              label={
                superseded
                  ? t("Superseded package")
                  : view.fullyAcknowledged
                    ? t("Fully acknowledged")
                    : t("Acknowledgements pending")
              }
              tone={
                superseded
                  ? "neutral"
                  : view.fullyAcknowledged
                    ? "success"
                    : "warning"
              }
            />
            <p className="production-transition-workspace__disclaimer">
              {t(
                "This immutable technical package does not close G7 or change Project, Work Item, Tooling, Gate, or ERP truth.",
              )}
            </p>
          </div>
          <DefinitionList
            rows={[
              {
                label: t("Package revision"),
                value: formatNumber(locale, revision.handoverVersion),
              },
              {
                exempt: "identifier",
                label: t("Policy version"),
                value: `${String(revision.policyRef.version)} · ${revision.policyRef.globalId}`,
              },
              {
                exempt: "business-data",
                label: t("Created by"),
                value: revision.createdByUserId,
              },
              {
                label: t("Created at"),
                value: formatDateTime(locale, revision.createdAt),
              },
            ]}
          />
        </div>
      </Panel>

      <Panel
        bodyClassName="production-transition-workspace__table-body"
        scrollableBody
        title={t("Frozen receiving groups and acknowledgement slots")}
      >
        <table className="engineering-table engineering-table--compact">
          <caption className="visually-hidden">
            {t("Frozen receiving groups and acknowledgement slots")}
          </caption>
          <thead>
            <tr>
              <th scope="col">{t("Slot")}</th>
              <th scope="col">{t("Receiving group")}</th>
              <th scope="col">{t("Direction")}</th>
              <th scope="col">{t("Member")}</th>
              <th scope="col">{t("Project role")}</th>
              <th scope="col">{t("Acknowledgement")}</th>
            </tr>
          </thead>
          <tbody>
            {revision.slots.map((slot) => (
              <tr
                aria-selected={
                  selection?.kind === "slot" && selection.key === slot.slotKey
                }
                className={
                  selection?.kind === "slot" && selection.key === slot.slotKey
                    ? "engineering-table__row--selected"
                    : undefined
                }
                key={slot.slotKey}
              >
                <th scope="row">
                  <button
                    className="production-transition-workspace__row-select"
                    data-testid={`handover-slot-${slot.slotKey}`}
                    disabled={selectionLocked}
                    onClick={() => {
                      onSelect({ kind: "slot", key: slot.slotKey });
                    }}
                    type="button"
                  >
                    <code data-language-exempt="identifier">
                      {slot.slotKey}
                    </code>
                  </button>
                </th>
                <td>
                  <code data-language-exempt="identifier">{slot.groupKey}</code>
                </td>
                <td>{directionLabel(t, slot.direction)}</td>
                <td data-language-exempt="business-data">
                  {slot.member.userId}
                </td>
                <td>
                  <code data-language-exempt="identifier">
                    {slot.role.roleKey}
                  </code>
                </td>
                <td>
                  <SemanticStatus
                    label={
                      acknowledged.has(slot.slotKey)
                        ? t("Acknowledged")
                        : t("Pending")
                    }
                    tone={
                      acknowledged.has(slot.slotKey) ? "success" : "warning"
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel
        bodyClassName="production-transition-workspace__table-body"
        scrollableBody
        title={t("Frozen handover manifest")}
      >
        {revision.manifest.length ? (
          <table className="engineering-table engineering-table--compact">
            <caption className="visually-hidden">
              {t("Frozen handover manifest")}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("Requirement")}</th>
                <th scope="col">{t("Manifest role")}</th>
                <th scope="col">{t("Source kind")}</th>
                <th scope="col">{t("Version")}</th>
                <th scope="col">{t("Exact identity")}</th>
              </tr>
            </thead>
            <tbody>
              {revision.manifest.map((source) => {
                const key = `${source.requirementKey}:${source.kind}:${source.globalId}`;
                return (
                  <tr
                    aria-selected={
                      selection?.kind === "manifest" && selection.key === key
                    }
                    className={
                      selection?.kind === "manifest" && selection.key === key
                        ? "engineering-table__row--selected"
                        : undefined
                    }
                    key={key}
                  >
                    <th scope="row">
                      <button
                        className="production-transition-workspace__row-select"
                        data-testid={`manifest-${source.requirementKey}-${source.kind}`}
                        disabled={selectionLocked}
                        onClick={() => {
                          onSelect({ kind: "manifest", key });
                        }}
                        type="button"
                      >
                        <code data-language-exempt="identifier">
                          {source.requirementKey}
                        </code>
                      </button>
                    </th>
                    <td>
                      <code data-language-exempt="identifier">
                        {source.role}
                      </code>
                    </td>
                    <td>{sourceKindLabel(t, source.kind)}</td>
                    <td>{formatNumber(locale, source.sourceVersion)}</td>
                    <td>
                      <code data-language-exempt="identifier">
                        {source.globalId}
                      </code>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p>{t("No exact manifest sources are retained.")}</p>
        )}
      </Panel>

      <Panel
        bodyClassName="production-transition-workspace__table-body"
        scrollableBody
        title={t("Unresolved actions at package freeze")}
      >
        {revision.unresolvedActions.length > maximumUnresolvedActions ? (
          <div role="alert">
            <SemanticStatus label={t("Validation error")} tone="danger" />
            <p>
              {t(
                "The unresolved action result exceeds the maximum of 10,000 rows.",
              )}
            </p>
          </div>
        ) : null}
        {boundedUnresolved.length ? (
          <>
            <table className="engineering-table engineering-table--compact">
              <caption className="visually-hidden">
                {t("Unresolved actions at package freeze")}
              </caption>
              <thead>
                <tr>
                  <th scope="col">{t("Work item")}</th>
                  <th scope="col">{t("Kind")}</th>
                  <th scope="col">{t("Retained state")}</th>
                  <th scope="col">{t("Owner")}</th>
                  <th scope="col">{t("Due date")}</th>
                  <th scope="col">{t("Version")}</th>
                </tr>
              </thead>
              <tbody>
                {visibleUnresolved.map((item) => (
                  <tr
                    aria-selected={
                      selection?.kind === "unresolved" &&
                      selection.key === item.globalId
                    }
                    className={
                      selection?.kind === "unresolved" &&
                      selection.key === item.globalId
                        ? "engineering-table__row--selected"
                        : undefined
                    }
                    key={item.globalId}
                  >
                    <th scope="row">
                      <button
                        className="production-transition-workspace__row-select"
                        disabled={selectionLocked}
                        onClick={() => {
                          onSelect({
                            kind: "unresolved",
                            key: item.globalId,
                          });
                        }}
                        type="button"
                      >
                        <code data-language-exempt="identifier">
                          {item.globalId}
                        </code>
                      </button>
                    </th>
                    <td>{workKindLabel(t, item.kind)}</td>
                    <td>{workStateLabel(t, item.state)}</td>
                    <td data-language-exempt="business-data">
                      {item.ownerUserId}
                    </td>
                    <td>{formatDate(locale, item.dueDate)}</td>
                    <td>{formatNumber(locale, item.sourceVersion)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination
              currentPage={currentPage}
              itemCount={boundedUnresolved.length}
              onPageChange={setPage}
            />
          </>
        ) : (
          <p>{t("No unresolved actions were present at package freeze.")}</p>
        )}
      </Panel>
    </div>
  );
}

function ObservationInspector({
  providers,
  revision,
  selection,
  superseded,
}: {
  providers: readonly ProductionTransitionExternalUnavailableProvider[];
  revision: ObservationPeriodRevision | null;
  selection: InspectorSelection | null;
  superseded: boolean;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const provider =
    selection?.kind === "provider"
      ? (providers.find((item) => item.kind === selection.key) ?? null)
      : null;
  const references = revision
    ? [...revision.contextReferences, ...revision.retrospectiveReferences]
    : [];
  const reference =
    selection?.kind === "observation-reference"
      ? (references.find(
          (item) =>
            `${item.usage}:${item.kind}:${item.globalId}` === selection.key,
        ) ?? null)
      : null;
  return (
    <DockedInspector
      id="production-transition-inspector"
      title={t("Observation inspector")}
    >
      <div data-testid="production-transition-inspector">
        <SemanticStatus
          label={superseded ? t("Superseded") : t("Not evaluable")}
          tone={superseded ? "neutral" : "warning"}
        />
        <p className="production-transition-workspace__disclaimer">
          {t(
            "Observation is technical review truth only. It is not formal production stability, acceptance, approval, or a Gate decision.",
          )}
        </p>
        {provider ? (
          <>
            <h3>{providerLabel(t, provider.kind)}</h3>
            <DefinitionList
              rows={[
                { label: t("Provider state"), value: t("Unavailable") },
                {
                  exempt: "identifier",
                  label: t("Reason code"),
                  value: provider.reasonCode,
                },
                { label: t("Source identity"), value: t("Not available") },
                { label: t("Observed at"), value: t("Not available") },
                { label: t("Value"), value: t("Not available") },
              ]}
            />
            <p>{providerReason(t, provider)}</p>
          </>
        ) : reference ? (
          <DefinitionList
            rows={[
              {
                label: t("Usage"),
                value:
                  reference.usage === "context"
                    ? t("Review context")
                    : t("Retrospective evidence"),
              },
              {
                label: t("Source kind"),
                value: sourceKindLabel(t, reference.kind),
              },
              {
                exempt: "identifier",
                label: t("Source identity"),
                value: reference.globalId,
              },
              {
                label: t("Source version"),
                value: formatNumber(locale, reference.sourceVersion),
              },
              {
                exempt: "identifier",
                label: t("Snapshot hash"),
                value: reference.snapshotHash,
              },
            ]}
          />
        ) : (
          <p>{t("Select an unavailable provider or exact reference.")}</p>
        )}
      </div>
    </DockedInspector>
  );
}

function ObservationContent({
  onSelect,
  providers,
  revision,
  selection,
  superseded,
}: {
  onSelect: (selection: InspectorSelection) => void;
  providers: readonly ProductionTransitionExternalUnavailableProvider[];
  revision: ObservationPeriodRevision | null;
  selection: InspectorSelection | null;
  superseded: boolean;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const references = revision
    ? [...revision.contextReferences, ...revision.retrospectiveReferences]
    : [];
  return (
    <div className="production-transition-workspace__content">
      <Panel
        className="production-transition-workspace__summary"
        scrollableBody
        title={t("Observation period")}
      >
        <div className="production-transition-workspace__summary-grid">
          <div>
            <SemanticStatus
              label={superseded ? t("Superseded") : t("Not evaluable")}
              tone={superseded ? "neutral" : "warning"}
            />
            <p className="production-transition-workspace__disclaimer">
              {t(
                "Actual SOP and all mandatory production providers remain unavailable. No observed window, zero value, success, or stable conclusion is inferred.",
              )}
            </p>
          </div>
          {revision ? (
            <DefinitionList
              rows={[
                {
                  label: t("Observation revision"),
                  value: formatNumber(locale, revision.observationVersion),
                },
                { label: t("Observation state"), value: t("Not evaluable") },
                {
                  label: t("Technical disposition"),
                  value: t("Not evaluable"),
                },
                {
                  label: t("Observed window"),
                  value: t("Not available"),
                },
              ]}
            />
          ) : (
            <p>{t("No observation revision has been retained.")}</p>
          )}
        </div>
      </Panel>

      <Panel
        bodyClassName="production-transition-workspace__table-body"
        scrollableBody
        title={t("Mandatory external providers")}
      >
        <table
          className="engineering-table engineering-table--compact"
          data-testid="production-transition-providers"
        >
          <caption className="visually-hidden">
            {t("Mandatory external providers")}
          </caption>
          <thead>
            <tr>
              <th scope="col">{t("Provider")}</th>
              <th scope="col">{t("State")}</th>
              <th scope="col">{t("Reason code")}</th>
              <th scope="col">{t("Source identity")}</th>
              <th scope="col">{t("Value")}</th>
            </tr>
          </thead>
          <tbody>
            {providers.map((provider) => (
              <tr
                aria-selected={
                  selection?.kind === "provider" &&
                  selection.key === provider.kind
                }
                className={
                  selection?.kind === "provider" &&
                  selection.key === provider.kind
                    ? "engineering-table__row--selected"
                    : undefined
                }
                key={provider.kind}
              >
                <th scope="row">
                  <button
                    className="production-transition-workspace__row-select"
                    data-testid={`provider-${provider.kind}`}
                    onClick={() => {
                      onSelect({ kind: "provider", key: provider.kind });
                    }}
                    type="button"
                  >
                    {providerLabel(t, provider.kind)}
                  </button>
                </th>
                <td>
                  <SemanticStatus label={t("Unavailable")} tone="warning" />
                </td>
                <td>
                  <code data-language-exempt="identifier">
                    {provider.reasonCode}
                  </code>
                </td>
                <td>{t("Not available")}</td>
                <td>{t("Not available")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel
        bodyClassName="production-transition-workspace__table-body"
        scrollableBody
        title={t("Exact observation references")}
      >
        {references.length ? (
          <table className="engineering-table engineering-table--compact">
            <caption className="visually-hidden">
              {t("Exact observation references")}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("Usage")}</th>
                <th scope="col">{t("Source kind")}</th>
                <th scope="col">{t("Version")}</th>
                <th scope="col">{t("Exact identity")}</th>
              </tr>
            </thead>
            <tbody>
              {references.map((reference) => {
                const key = `${reference.usage}:${reference.kind}:${reference.globalId}`;
                return (
                  <tr
                    aria-selected={
                      selection?.kind === "observation-reference" &&
                      selection.key === key
                    }
                    className={
                      selection?.kind === "observation-reference" &&
                      selection.key === key
                        ? "engineering-table__row--selected"
                        : undefined
                    }
                    key={key}
                  >
                    <th scope="row">
                      <button
                        className="production-transition-workspace__row-select"
                        onClick={() => {
                          onSelect({ kind: "observation-reference", key });
                        }}
                        type="button"
                      >
                        {reference.usage === "context"
                          ? t("Review context")
                          : t("Retrospective evidence")}
                      </button>
                    </th>
                    <td>{sourceKindLabel(t, reference.kind)}</td>
                    <td>{formatNumber(locale, reference.sourceVersion)}</td>
                    <td>
                      <code data-language-exempt="identifier">
                        {reference.globalId}
                      </code>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p>{t("No exact observation references are retained.")}</p>
        )}
      </Panel>

      {revision ? (
        <Panel title={t("Retrospective note and authority boundary")}>
          <DefinitionList
            rows={[
              {
                label: t("Retrospective note"),
                value: revision.retrospectiveNote ?? t("Not available"),
                ...(revision.retrospectiveNote
                  ? { exempt: "business-data" as const }
                  : {}),
              },
              {
                exempt: "identifier",
                label: t("Authority boundary"),
                value: revision.authorityBoundary,
              },
              {
                exempt: "identifier",
                label: t("Handover package reference"),
                value:
                  revision.handoverPackageRef?.globalId ?? t("Not available"),
              },
            ]}
          />
        </Panel>
      ) : null}
    </div>
  );
}

function mergeHandoverHistory(
  workspace: ProductionTransitionWorkspace,
): readonly HandoverPackageView[] {
  const entries = [...workspace.handoverHistory];
  if (
    workspace.currentHandover &&
    !entries.some(
      (item) =>
        item.revision.globalId === workspace.currentHandover?.revision.globalId,
    )
  ) {
    entries.push(workspace.currentHandover);
  }
  return entries.sort(
    (left, right) =>
      left.revision.handoverVersion - right.revision.handoverVersion,
  );
}

function mergeObservationHistory(
  workspace: ProductionTransitionWorkspace,
): readonly ObservationPeriodRevision[] {
  const entries = [...workspace.observationHistory];
  if (
    workspace.currentObservation &&
    !entries.some(
      (item) => item.globalId === workspace.currentObservation?.globalId,
    )
  ) {
    entries.push(workspace.currentObservation);
  }
  return entries.sort(
    (left, right) => left.observationVersion - right.observationVersion,
  );
}

export interface ProjectProductionTransitionWorkspaceProps {
  readonly dataSource: ProductionTransitionDataSource;
  readonly projectId: string;
}

export function ProjectProductionTransitionWorkspace({
  dataSource,
  projectId,
}: ProjectProductionTransitionWorkspaceProps): React.JSX.Element {
  const { sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [view, setView] = useState<WorkspaceView>("handover");
  const [selectedHandoverRevisionId, setSelectedHandoverRevisionId] = useState<
    string | null
  >(null);
  const [selectedObservationRevisionId, setSelectedObservationRevisionId] =
    useState<string | null>(null);
  const [selection, setSelection] = useState<InspectorSelection | null>(null);
  const [selectedAcknowledgementSlotKey, setSelectedAcknowledgementSlotKey] =
    useState<string | null | undefined>(undefined);
  const [unresolvedPage, setUnresolvedPage] = useState(0);
  const [commandState, setCommandState] = useState<CommandState>({
    kind: "idle",
  });
  const [review, setReview] = useState<RetryableAcknowledgement | null>(null);
  const commandController = useRef<AbortController | null>(null);
  const retryCommand = useRef<RetryableAcknowledgement | null>(null);

  const acceptWorkspace = useCallback(
    (workspace: ProductionTransitionWorkspace): void => {
      setResource({ kind: "loaded", value: workspace });
      setSelectedHandoverRevisionId(
        workspace.currentHandover?.revision.globalId ?? null,
      );
      setSelectedObservationRevisionId(
        workspace.currentObservation?.globalId ?? null,
      );
      const firstSlot = workspace.currentHandover?.revision.slots[0];
      const firstProvider = workspace.unavailableProviders[0];
      setSelection(
        firstSlot
          ? { kind: "slot", key: firstSlot.slotKey }
          : { kind: "provider", key: firstProvider.kind },
      );
      setSelectedAcknowledgementSlotKey(undefined);
      setUnresolvedPage(0);
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    void dataSource
      .loadWorkspace(projectId, controller.signal)
      .then((workspace) => {
        if (!controller.signal.aborted) acceptWorkspace(workspace);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setResource({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [acceptWorkspace, attempt, dataSource, projectId]);

  useEffect(
    () => () => {
      commandController.current?.abort();
    },
    [],
  );

  const reload = useCallback((): void => {
    commandController.current?.abort();
    retryCommand.current = null;
    setReview(null);
    setCommandState({ kind: "idle" });
    setResource({ kind: "loading" });
    setAttempt((value) => value + 1);
  }, []);

  const workspace = resource.kind === "loaded" ? resource.value : null;
  const handoverHistory = useMemo(
    () => (workspace ? mergeHandoverHistory(workspace) : []),
    [workspace],
  );
  const observationHistory = useMemo(
    () => (workspace ? mergeObservationHistory(workspace) : []),
    [workspace],
  );
  const selectedHandover =
    handoverHistory.find(
      (item) => item.revision.globalId === selectedHandoverRevisionId,
    ) ??
    workspace?.currentHandover ??
    null;
  const selectedObservation =
    observationHistory.find(
      (item) => item.globalId === selectedObservationRevisionId,
    ) ??
    workspace?.currentObservation ??
    null;
  const handoverSuperseded = Boolean(
    selectedHandover &&
    workspace?.currentHandover &&
    selectedHandover.revision.globalId !==
      workspace.currentHandover.revision.globalId,
  );
  const observationSuperseded = Boolean(
    selectedObservation &&
    workspace?.currentObservation &&
    selectedObservation.globalId !== workspace.currentObservation.globalId,
  );

  const acknowledgementEligibility = useMemo<AcknowledgementEligibility>(() => {
    if (!workspace || !selectedHandover || handoverSuperseded) {
      return { candidates: [], hold: null };
    }
    if (selectedHandover.fullyAcknowledged) {
      return {
        candidates: [],
        hold: t("Every frozen slot is acknowledged."),
      };
    }
    if (!sessionCommandContext) return { candidates: [], hold: null };
    const permissionKeys = [
      ...new Set(workspace.permissions.canAcknowledgeSlots),
    ];
    if (permissionKeys.length === 0) {
      return {
        candidates: [],
        hold: t("You do not have permission to acknowledge a frozen slot."),
      };
    }
    const acknowledged = new Set(
      selectedHandover.acknowledgements.map((item) => item.slotKey),
    );
    const permissionKeySet = new Set(permissionKeys);
    const candidates = selectedHandover.revision.slots.filter(
      (slot) =>
        permissionKeySet.has(slot.slotKey) &&
        slot.member.userId === sessionCommandContext.userId &&
        !acknowledged.has(slot.slotKey),
    );
    if (candidates.length !== permissionKeys.length) {
      return {
        candidates: [],
        hold: t(
          "The acknowledgement permission does not match the current actor and frozen slot.",
        ),
      };
    }
    return { candidates, hold: null };
  }, [
    handoverSuperseded,
    selectedHandover,
    sessionCommandContext,
    t,
    workspace,
  ]);

  const automaticAcknowledgementCandidate =
    selectedAcknowledgementSlotKey === undefined &&
    acknowledgementEligibility.candidates.length === 1
      ? (acknowledgementEligibility.candidates[0] ?? null)
      : null;
  const resolvedAcknowledgementSlotKey =
    automaticAcknowledgementCandidate?.slotKey ??
    selectedAcknowledgementSlotKey ??
    null;
  const handoverSelection: InspectorSelection | null =
    automaticAcknowledgementCandidate
      ? { kind: "slot", key: automaticAcknowledgementCandidate.slotKey }
      : selectedAcknowledgementSlotKey === undefined &&
          acknowledgementEligibility.candidates.length > 1
        ? null
        : selection;

  const acknowledgementCandidate =
    handoverSelection?.kind === "slot" &&
    handoverSelection.key === resolvedAcknowledgementSlotKey
      ? (acknowledgementEligibility.candidates.find(
          (slot) => slot.slotKey === resolvedAcknowledgementSlotKey,
        ) ?? null)
      : null;

  const execute = useCallback(
    (operation: RetryableAcknowledgement): void => {
      if (!sessionCommandContext) return;
      commandController.current?.abort();
      const controller = new AbortController();
      commandController.current = controller;
      setCommandState({ kind: "processing" });
      void (async () => {
        try {
          const result = await dataSource.acknowledgeSlot(
            projectId,
            operation.handoverId,
            operation.handoverVersion,
            operation.command,
            {
              csrfToken: sessionCommandContext.csrfToken,
              idempotencyKey: operation.idempotencyKey,
              signal: controller.signal,
            },
          );
          retryCommand.current = null;
          try {
            const refreshed = await dataSource.loadWorkspace(
              projectId,
              controller.signal,
            );
            if (controller.signal.aborted) return;
            acceptWorkspace(refreshed);
            setCommandState({
              kind: "succeeded",
              refreshFailure: null,
              replayed: result.replayed,
            });
          } catch (refreshError: unknown) {
            if (controller.signal.aborted) return;
            setCommandState({
              kind: "succeeded",
              refreshFailure: toRequestFailure(refreshError),
              replayed: result.replayed,
            });
          }
        } catch (error: unknown) {
          if (controller.signal.aborted) return;
          setCommandState({
            kind: "failed",
            failure: toRequestFailure(error),
          });
        }
      })();
    },
    [acceptWorkspace, dataSource, projectId, sessionCommandContext],
  );

  const prepareAcknowledgement = useCallback((): void => {
    if (
      !selectedHandover ||
      !acknowledgementCandidate ||
      !sessionCommandContext ||
      handoverSuperseded ||
      commandState.kind !== "idle"
    )
      return;
    const operation: RetryableAcknowledgement = {
      command: {
        expectedRevisionGlobalId: selectedHandover.revision.globalId,
        expectedSnapshotHash: selectedHandover.revision.snapshotHash,
        intent: "acknowledge",
        slotKey: acknowledgementCandidate.slotKey,
      },
      handoverId: selectedHandover.revision.handoverGlobalId,
      handoverVersion: selectedHandover.revision.handoverVersion,
      idempotencyKey: `production-handover-ack-${globalThis.crypto.randomUUID()}`,
    };
    retryCommand.current = operation;
    setReview(operation);
  }, [
    acknowledgementCandidate,
    commandState.kind,
    handoverSuperseded,
    selectedHandover,
    sessionCommandContext,
  ]);

  const retry = useCallback((): void => {
    const operation = retryCommand.current;
    if (operation) execute(operation);
  }, [execute]);

  if (resource.kind === "loading") return <LoadingState />;
  if (resource.kind === "failed") {
    return <FailureState failure={resource.failure} onRetry={reload} />;
  }

  const isEmpty =
    handoverHistory.length === 0 && observationHistory.length === 0;
  const handoverNavigationLocked =
    review !== null ||
    commandState.kind === "processing" ||
    commandState.kind === "failed" ||
    (commandState.kind === "succeeded" && commandState.refreshFailure !== null);
  const selectAcknowledgementCandidate = (slotKey: string | null): void => {
    if (handoverNavigationLocked) return;
    const candidate = acknowledgementEligibility.candidates.find(
      (slot) => slot.slotKey === slotKey,
    );
    setSelectedAcknowledgementSlotKey(candidate?.slotKey ?? null);
    setSelection(candidate ? { kind: "slot", key: candidate.slotKey } : null);
  };
  const selectHandoverFact = (nextSelection: InspectorSelection): void => {
    if (handoverNavigationLocked) return;
    setSelection(nextSelection);
    if (nextSelection.kind !== "slot") {
      setSelectedAcknowledgementSlotKey(null);
      return;
    }
    const candidate = acknowledgementEligibility.candidates.find(
      (slot) => slot.slotKey === nextSelection.key,
    );
    setSelectedAcknowledgementSlotKey(candidate?.slotKey ?? null);
  };
  const activateView = (nextView: WorkspaceView): void => {
    setView(nextView);
    if (nextView === "handover") {
      const preferredSlot = acknowledgementEligibility.candidates.find(
        (slot) => slot.slotKey === resolvedAcknowledgementSlotKey,
      );
      const slot =
        preferredSlot ??
        (acknowledgementEligibility.candidates.length === 1
          ? acknowledgementEligibility.candidates[0]
          : selectedHandover?.revision.slots[0]);
      setSelection(slot ? { kind: "slot", key: slot.slotKey } : null);
      return;
    }
    const provider = resource.value.unavailableProviders[0];
    setSelection({ kind: "provider", key: provider.kind });
  };
  const handleViewTabKey = (
    event: KeyboardEvent<HTMLElement>,
    currentView: WorkspaceView,
  ): void => {
    let nextView: WorkspaceView | null = null;
    if (event.key === "Home") nextView = "handover";
    if (event.key === "End") nextView = "observation";
    if (event.key === "ArrowRight") {
      nextView = currentView === "handover" ? "observation" : "handover";
    }
    if (event.key === "ArrowLeft") {
      nextView = currentView === "handover" ? "observation" : "handover";
    }
    if (!nextView) return;
    event.preventDefault();
    activateView(nextView);
    void focusControl(
      document.getElementById(`production-transition-${nextView}-tab`),
    );
  };
  return (
    <section
      aria-label={t("Production transition")}
      className="production-transition-workspace"
      data-testid="production-transition-workspace"
    >
      <div className="production-transition-workspace__toolbar">
        <div
          aria-label={t("Production transition views")}
          className="rectangular-tabs"
          role="tablist"
        >
          <button
            aria-controls="production-transition-handover-view"
            aria-selected={view === "handover"}
            data-testid="production-transition-handover-tab"
            id="production-transition-handover-tab"
            onKeyDown={(event) => {
              handleViewTabKey(event, "handover");
            }}
            onClick={() => {
              activateView("handover");
            }}
            role="tab"
            tabIndex={view === "handover" ? 0 : -1}
            type="button"
          >
            {t("Handover package")}
          </button>
          <button
            aria-controls="production-transition-observation-view"
            aria-selected={view === "observation"}
            data-testid="production-transition-observation-tab"
            id="production-transition-observation-tab"
            onKeyDown={(event) => {
              handleViewTabKey(event, "observation");
            }}
            onClick={() => {
              activateView("observation");
            }}
            role="tab"
            tabIndex={view === "observation" ? 0 : -1}
            type="button"
          >
            {t("Observation period")}
          </button>
        </div>
        <SemanticStatus label={t("NPI technical truth only")} tone="info" />
      </div>

      {view === "handover" ? (
        isEmpty ? (
          <div
            aria-labelledby="production-transition-handover-tab"
            className="production-transition-workspace__empty"
            data-testid="production-transition-empty"
            id="production-transition-handover-view"
            role="tabpanel"
          >
            <SemanticStatus label={t("Empty")} tone="neutral" />
            <h2>{t("No production transition history")}</h2>
            <p>
              {t(
                "No handover package or observation revision has been retained. This workspace does not create or revise them.",
              )}
            </p>
          </div>
        ) : (
          <div
            aria-labelledby="production-transition-handover-tab"
            className="production-transition-workspace__layout"
            id="production-transition-handover-view"
            role="tabpanel"
          >
            <HandoverHistory
              currentRevisionId={
                resource.value.currentHandover?.revision.globalId ?? null
              }
              history={handoverHistory}
              navigationLocked={handoverNavigationLocked}
              onSelect={(entry) => {
                if (handoverNavigationLocked) return;
                setSelectedHandoverRevisionId(entry.revision.globalId);
                setSelectedAcknowledgementSlotKey(undefined);
                setSelection(
                  entry.revision.slots[0]
                    ? { kind: "slot", key: entry.revision.slots[0].slotKey }
                    : null,
                );
                setUnresolvedPage(0);
                setCommandState({ kind: "idle" });
                setReview(null);
              }}
              selectedRevisionId={selectedHandover?.revision.globalId ?? null}
            />
            {selectedHandover ? (
              <>
                <HandoverContent
                  onSelect={selectHandoverFact}
                  page={unresolvedPage}
                  selection={handoverSelection}
                  selectionLocked={handoverNavigationLocked}
                  setPage={setUnresolvedPage}
                  superseded={handoverSuperseded}
                  view={selectedHandover}
                />
                <HandoverInspector
                  candidate={acknowledgementCandidate}
                  commandState={commandState}
                  eligibleCandidates={acknowledgementEligibility.candidates}
                  onPrepareAcknowledgement={prepareAcknowledgement}
                  onReload={reload}
                  onRetry={retry}
                  onSelectCandidate={selectAcknowledgementCandidate}
                  permissionHold={acknowledgementEligibility.hold}
                  selection={handoverSelection}
                  selectionLocked={handoverNavigationLocked}
                  superseded={handoverSuperseded}
                  view={selectedHandover}
                />
              </>
            ) : (
              <>
                <Panel title={t("Handover package")}>
                  <p>{t("No handover package has been retained.")}</p>
                </Panel>
                <DockedInspector title={t("Production transition inspector")}>
                  <p>{t("No exact handover fact is available to inspect.")}</p>
                </DockedInspector>
              </>
            )}
          </div>
        )
      ) : (
        <div
          aria-labelledby="production-transition-observation-tab"
          className="production-transition-workspace__layout"
          id="production-transition-observation-view"
          role="tabpanel"
        >
          <ObservationHistory
            currentRevisionId={
              resource.value.currentObservation?.globalId ?? null
            }
            history={observationHistory}
            onSelect={(revision) => {
              setSelectedObservationRevisionId(revision.globalId);
              const provider = revision.providers[0];
              setSelection({ kind: "provider", key: provider.kind });
            }}
            selectedRevisionId={selectedObservation?.globalId ?? null}
          />
          <ObservationContent
            onSelect={setSelection}
            providers={
              selectedObservation?.providers ??
              resource.value.unavailableProviders
            }
            revision={selectedObservation}
            selection={selection}
            superseded={observationSuperseded}
          />
          <ObservationInspector
            providers={
              selectedObservation?.providers ??
              resource.value.unavailableProviders
            }
            revision={selectedObservation}
            selection={selection}
            superseded={observationSuperseded}
          />
        </div>
      )}

      {review && selectedHandover && acknowledgementCandidate ? (
        <ImpactReview
          confirmLabel={t("Acknowledge exact slot")}
          contextRows={[
            {
              exempt: "identifier",
              label: t("Package revision"),
              value: String(selectedHandover.revision.handoverVersion),
            },
            {
              exempt: "identifier",
              label: t("Slot key"),
              value: acknowledgementCandidate.slotKey,
            },
            {
              exempt: "business-data",
              label: t("Current actor"),
              value: acknowledgementCandidate.member.userId,
            },
          ]}
          details={{
            audit: t(
              "The actor-bound acknowledgement, receipt, and audit are appended atomically.",
            ),
            failureHandling: t(
              "A failed transaction retains no partial acknowledgement. Retry uses the same command identity.",
            ),
            impact: t(
              "Appends one immutable acknowledgement fact to this exact current package and frozen slot.",
            ),
            irreversible: t(
              "The acknowledgement fact cannot be overwritten or copied to a successor package.",
            ),
            objectIdentity: acknowledgementCandidate.slotKey,
            permission: t(
              "Only the authenticated enabled member frozen into this exact slot can acknowledge it.",
            ),
            version: t("Package revision {{version}}", {
              version: selectedHandover.revision.handoverVersion,
            }),
          }}
          onCancel={() => {
            setReview(null);
          }}
          onConfirm={() => {
            setReview(null);
            execute(review);
          }}
          reasonRequired={false}
          returnFocusTarget={() =>
            document.getElementById("acknowledge-exact-slot")
          }
          title={t("Review exact acknowledgement")}
        />
      ) : null}
    </section>
  );
}
