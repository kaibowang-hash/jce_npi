import { useEffect, useMemo, useRef, useState } from "react";

import {
  integrationOperationKinds,
  integrationOperationStates,
  type IntegrationOperationActionKind,
  type IntegrationOperationActionResult,
  type IntegrationOperationCollection,
  type IntegrationOperationDetail,
  type IntegrationOperationFilters,
  type IntegrationOperationItem,
  type IntegrationOperationKind,
  type IntegrationOperationsDataSource,
  type IntegrationOperationState,
} from "../api/integration-operations-data-source";
import {
  NpiApiError,
  toRequestFailure,
  type RequestFailure,
} from "../api/http";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select } from "../ui-adapters/npi-ui";

type T = ReturnType<typeof useI18n>["t"];
type ResourceState =
  | { kind: "loading" }
  | { kind: "loaded"; value: IntegrationOperationCollection }
  | { kind: "failed"; failure: RequestFailure };
type DetailState =
  | { kind: "idle" }
  | { kind: "loading"; operationId: string }
  | { kind: "loaded"; value: IntegrationOperationDetail }
  | { kind: "failed"; operationId: string; failure: RequestFailure };
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; action: IntegrationOperationActionKind }
  | {
      kind: "succeeded";
      action: IntegrationOperationActionKind;
      result: IntegrationOperationActionResult;
    }
  | {
      kind: "failed";
      action: IntegrationOperationActionKind;
      failure: RequestFailure;
      conflict: boolean;
    };

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

function operationLabel(t: T, kind: IntegrationOperationKind): string {
  switch (kind) {
    case "receive_project_submission":
      return t("Receive Project submission");
    case "publish_item":
      return t("Publish Item");
    case "publish_mbom":
      return t("Publish MBOM");
    case "create_tool_asset":
      return t("Create Tool Asset");
    case "update_tool_asset":
      return t("Update Tool Asset");
    case "receive_engineering_change_event":
      return t("Receive engineering change event");
    case "publish_change_implementation_summary":
      return t("Publish change implementation summary");
  }
}

function stateLabel(t: T, state: IntegrationOperationState): string {
  switch (state) {
    case "queued":
      return t("Queued");
    case "processing":
      return t("Processing");
    case "succeeded":
      return t("Succeeded");
    case "failed_retryable":
      return t("Failed, replay available");
    case "failed_final":
      return t("Final failure");
    case "uncertain":
      return t("Outcome uncertain");
    case "partial":
      return t("Partial result");
    case "conflict":
      return t("Identity or version conflict");
    case "quarantined":
      return t("Quarantined");
    case "unavailable":
      return t("Evidence unavailable");
  }
}

function stateTone(
  state: IntegrationOperationState,
): "neutral" | "info" | "success" | "warning" | "danger" {
  if (state === "succeeded") return "success";
  if (state === "queued" || state === "processing") return "info";
  if (state === "failed_final" || state === "quarantined") return "danger";
  if (
    state === "failed_retryable" ||
    state === "uncertain" ||
    state === "partial" ||
    state === "conflict"
  )
    return "warning";
  return "neutral";
}

function faultLabel(
  t: T,
  fault: IntegrationOperationItem["faultClass"],
): string {
  switch (fault) {
    case "none":
      return t("No classified fault");
    case "retryable_before_uncertain_boundary":
      return t("Retryable before the target boundary");
    case "final_business_failure":
      return t("Final business failure");
    case "uncertain_after_boundary":
      return t("Uncertain after the target boundary");
    case "partial_result":
      return t("Partial target result");
    case "identity_conflict":
      return t("Identity or version conflict");
    case "authenticity_quarantine":
      return t("Authenticity quarantine");
    case "target_unavailable":
      return t("Target evidence unavailable");
    case "unknown_raw_state":
      return t("Unknown owning state");
  }
}

function availableAction(
  item: IntegrationOperationItem,
): IntegrationOperationActionKind | null {
  if (
    item.operationKind === "receive_engineering_change_event" ||
    item.operationKind === "publish_change_implementation_summary"
  ) {
    return null;
  }
  if (item.replayEligible) return "replay";
  if (item.reconciliationRequired) return "request_reconciliation";
  return null;
}

function actionLabel(t: T, action: IntegrationOperationActionKind): string {
  return action === "replay"
    ? t("Review and request replay")
    : t("Review and request reconciliation");
}

function LoadingSurface(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section
      aria-busy="true"
      aria-label={t("Loading integration operations")}
      className="workspace-resource-state workspace-resource-state--loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">
        {t("Loading integration operations")}
      </span>
    </section>
  );
}

function actionReviewDetails(
  t: T,
  operation: IntegrationOperationItem,
  action: IntegrationOperationActionKind,
) {
  return {
    objectIdentity: operation.operationGlobalId,
    version: `${operation.rawState} · v${String(operation.operationVersion)}`,
    impact:
      action === "replay"
        ? t(
            "The owning operation will reuse its exact immutable source and target idempotency. No new payload or target identity is supplied.",
          )
        : t(
            "This records reconciliation intent only. It does not assert target success, change a formal identity, or redispatch the operation.",
          ),
    permission: t(
      "The exact Project and operation-specific authority are verified again by the server.",
    ),
    irreversible: t(
      "The action receipt and audit history are append-only after the command commits.",
    ),
    failureHandling: t(
      "A conflict or failure remains visible without reporting ERPNext completion.",
    ),
    audit: t(
      "The server records the actor, trace, expected state, expected version and hashed idempotency identity. The review reason is not sent as business truth.",
    ),
  };
}

function DetailInspector({
  detail,
}: {
  detail: IntegrationOperationDetail;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const operation = detail.operation;
  return (
    <div className="integration-operation-inspector__content">
      <div className="detail-heading">
        <h2 data-language-exempt="identifier">{operation.operationGlobalId}</h2>
        <SemanticStatus
          label={stateLabel(t, operation.sharedState)}
          tone={stateTone(operation.sharedState)}
        />
      </div>
      <DefinitionList
        rows={[
          {
            label: t("Operation"),
            value: operationLabel(t, operation.operationKind),
          },
          {
            label: t("Owning state"),
            value: operation.rawState,
            exempt: "identifier",
          },
          {
            label: t("Fault classification"),
            value: faultLabel(t, operation.faultClass),
          },
          {
            label: t("Source identity"),
            value: operation.sourceGlobalId,
            exempt: "identifier",
          },
          {
            label: t("Operation version"),
            value: formatNumber(locale, operation.operationVersion, 0),
          },
          {
            label: t("Last updated"),
            value: formatDateTime(locale, operation.updatedAt),
          },
        ]}
      />
      <section aria-labelledby="operation-attempts-heading">
        <h3 id="operation-attempts-heading">{t("Attempts")}</h3>
        {operation.attempts.length ? (
          <div aria-label={t("Attempts")} className="table-scroll" tabIndex={0}>
            <table className="data-table data-table--compact">
              <thead>
                <tr>
                  <th className="integration-operation-compact-cell">
                    {t("Attempt")}
                  </th>
                  <th className="integration-operation-compact-cell">
                    {t("Owning state")}
                  </th>
                  <th className="integration-operation-compact-cell">
                    {t("Target boundary")}
                  </th>
                  <th className="integration-operation-compact-cell">
                    {t("Reconciliation")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {operation.attempts.map((attempt) => (
                  <tr key={`attempt-${String(attempt.attemptNumber)}`}>
                    <td className="integration-operation-compact-cell">
                      {formatNumber(locale, attempt.attemptNumber, 0)}
                    </td>
                    <td
                      className="integration-operation-compact-cell"
                      data-language-exempt="identifier"
                    >
                      {attempt.state}
                    </td>
                    <td className="integration-operation-compact-cell">
                      {attempt.adapterBoundaryCrossed
                        ? t("Crossed")
                        : t("Not crossed")}
                    </td>
                    <td className="integration-operation-compact-cell">
                      {attempt.reconciliationRequired
                        ? t("Required")
                        : t("Not required")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty-state-copy">
            {t("No attempt has been recorded.")}
          </p>
        )}
      </section>
      <section aria-labelledby="operation-results-heading">
        <h3 id="operation-results-heading">{t("Results")}</h3>
        {operation.results.length ? (
          <ul className="integration-operation-history">
            {operation.results.map((result) => (
              <li
                className="integration-operation-history-item"
                key={result.resultGlobalId}
              >
                <strong data-language-exempt="identifier">
                  {result.state}
                </strong>
                <span>
                  {result.authority === "authoritative_sandbox"
                    ? t("Authenticated Sandbox evidence")
                    : result.authority === "synthetic"
                      ? t("Synthetic evidence, not formal target truth")
                      : t("No target authority")}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty-state-copy">
            {t("No result has been recorded.")}
          </p>
        )}
      </section>
      <section aria-labelledby="operation-actions-heading">
        <h3 id="operation-actions-heading">{t("Action history")}</h3>
        {operation.actions.length ? (
          <ul className="integration-operation-history">
            {operation.actions.map((action) => (
              <li
                className="integration-operation-history-item"
                key={action.actionGlobalId}
              >
                <strong>
                  {action.actionKind === "replay"
                    ? t("Replay requested")
                    : t("Reconciliation requested")}
                </strong>
                <span data-language-exempt="identifier">
                  {action.actorUserId} · {action.traceId}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty-state-copy">
            {t("No operator action has been recorded.")}
          </p>
        )}
      </section>
    </div>
  );
}

export default function ExecutionPage({
  dataSource,
  projectId,
}: {
  dataSource: IntegrationOperationsDataSource;
  projectId: string;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const requestedId = new URLSearchParams(globalThis.location.search).get(
    "focus",
  );
  const initialSelectedId =
    requestedId && UUID.test(requestedId) ? requestedId : null;
  const [filters, setFilters] = useState<IntegrationOperationFilters>({
    limit: 50,
  });
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(
    initialSelectedId,
  );
  const selectedIdRef = useRef<string | null>(initialSelectedId);
  const [detail, setDetail] = useState<DetailState>({ kind: "idle" });
  const [reviewAction, setReviewAction] =
    useState<IntegrationOperationActionKind | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const actionButtonRef = useRef<HTMLElement | null>(null);
  const commandAbort = useRef<AbortController | null>(null);
  const projectReady = UUID.test(projectId);

  useEffect(() => {
    const refresh = (): void => {
      setResource({ kind: "loading" });
      setLoadAttempt((current) => current + 1);
    };
    globalThis.addEventListener("npi:refresh-integration-operations", refresh);
    return () => {
      globalThis.removeEventListener(
        "npi:refresh-integration-operations",
        refresh,
      );
    };
  }, []);

  useEffect(
    () => () => {
      commandAbort.current?.abort();
    },
    [],
  );

  useEffect(() => {
    if (!projectReady) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadOperations(projectId, filters, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setResource({ kind: "loaded", value });
        if (!value.permissions.view) {
          selectedIdRef.current = null;
          setSelectedId(null);
          setDetail({ kind: "idle" });
          return;
        }
        const current = selectedIdRef.current;
        const next =
          current &&
          value.items.some((item) => item.operationGlobalId === current)
            ? current
            : (value.items[0]?.operationGlobalId ?? null);
        selectedIdRef.current = next;
        setSelectedId(next);
        setDetail(
          next ? { kind: "loading", operationId: next } : { kind: "idle" },
        );
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setResource({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, filters, loadAttempt, projectId, projectReady]);

  const selected = useMemo(() => {
    if (resource.kind !== "loaded" || !selectedId) return null;
    return (
      resource.value.items.find(
        (item) => item.operationGlobalId === selectedId,
      ) ?? null
    );
  }, [resource, selectedId]);

  useEffect(() => {
    if (!selected) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadOperation(
        projectId,
        selected.operationKind,
        selected.operationGlobalId,
        controller.signal,
      )
      .then((value) => {
        if (!controller.signal.aborted) setDetail({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setDetail({
          kind: "failed",
          operationId: selected.operationGlobalId,
          failure: toRequestFailure(error),
        });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, projectId, selected]);

  const action = selected ? availableAction(selected) : null;
  const detailCanAct =
    detail.kind === "loaded" &&
    detail.value.operation.operationGlobalId === selected?.operationGlobalId &&
    detail.value.permissions.act;
  const detailPermissionDenied =
    detail.kind === "loaded" && !detail.value.permissions.act;
  const canAct =
    resource.kind === "loaded" &&
    resource.value.permissions.act &&
    detailCanAct &&
    sessionCommandContext !== null;
  const commandProcessing = command.kind === "processing";

  const requestCommand = (reason: string): void => {
    if (!selected || !reviewAction || !sessionCommandContext || !canAct) return;
    // The reason confirms deliberate review locally. The frozen API accepts no
    // caller-authored reason or target truth, so it is intentionally not sent.
    if (!reason.trim()) return;
    commandAbort.current?.abort();
    const controller = new AbortController();
    commandAbort.current = controller;
    const requestedAction = reviewAction;
    setReviewAction(null);
    setCommand({ kind: "processing", action: requestedAction });
    void dataSource
      .requestAction(projectId, selected, requestedAction, {
        csrfToken: sessionCommandContext.csrfToken,
        idempotencyKey: `p807-${requestedAction}-${globalThis.crypto.randomUUID()}`,
        signal: controller.signal,
      })
      .then((result) => {
        if (controller.signal.aborted) return;
        commandAbort.current = null;
        setCommand({ kind: "succeeded", action: requestedAction, result });
        setResource({ kind: "loading" });
        setLoadAttempt((current) => current + 1);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        commandAbort.current = null;
        setCommand({
          kind: "failed",
          action: requestedAction,
          failure: toRequestFailure(error),
          conflict:
            error instanceof NpiApiError && error.problem.status === 409,
        });
      });
  };

  if (!projectReady) {
    return (
      <article className="page page--execution">
        <header className="page-heading">
          <h1>{t("Integration operations")}</h1>
        </header>
        <Panel title={t("Project context required")}>
          <p>
            {t(
              "Open integration operations from an authorized Project. This workspace never uses a tenant-wide fallback.",
            )}
          </p>
        </Panel>
      </article>
    );
  }

  return (
    <article className="page page--execution">
      <header className="page-heading page-heading--actions">
        <div>
          <h1>{t("Integration operations")}</h1>
          <p>
            {t(
              "Inspect Project-scoped execution truth, logical DLQ classification, replay requests and reconciliation intent without treating them as ERPNext completion.",
            )}
          </p>
        </div>
        <Button
          onClick={() => {
            setResource({ kind: "loading" });
            setLoadAttempt((current) => current + 1);
          }}
        >
          {t("Refresh")}
        </Button>
      </header>

      {resource.kind === "loading" ? <LoadingSurface /> : null}
      {resource.kind === "failed" ? (
        <Panel title={t("Integration operations unavailable")}>
          <RequestFailurePanel failure={resource.failure} />
          <Button
            onClick={() => {
              setResource({ kind: "loading" });
              setLoadAttempt((current) => current + 1);
            }}
          >
            {t("Retry loading")}
          </Button>
        </Panel>
      ) : null}

      {resource.kind === "loaded" && !resource.value.permissions.view ? (
        <Panel title={t("Integration operations unavailable")}>
          <p>
            {t(
              "You do not have permission to view integration operations for this Project.",
            )}
          </p>
        </Panel>
      ) : null}

      {resource.kind === "loaded" && resource.value.permissions.view ? (
        <>
          {!resource.value.permissions.act ||
          detailPermissionDenied ||
          !sessionCommandContext ? (
            <div
              className="scenario-banner scenario-banner--read-only"
              role="status"
            >
              <strong>{t("Read-only integration view")}</strong>
              <span>
                {!resource.value.permissions.act || detailPermissionDenied
                  ? t(
                      "You may inspect Project-contained operation truth, but no operator action is authorized.",
                    )
                  : t(
                      "Session verification is required before an operator action can be submitted.",
                    )}
              </span>
            </div>
          ) : null}

          {command.kind === "processing" ? (
            <div
              aria-live="polite"
              className="scenario-banner scenario-banner--processing"
              role="status"
            >
              <strong>{t("Command in progress")}</strong>
              <span>
                {t(
                  "The exact operation state and version are being verified and committed atomically.",
                )}
              </span>
            </div>
          ) : null}
          {command.kind === "succeeded" ? (
            <div
              aria-live="polite"
              className="scenario-banner scenario-banner--success"
              role="status"
            >
              <strong>
                {command.action === "replay"
                  ? t("Replay request recorded")
                  : t("Reconciliation request recorded")}
              </strong>
              <span>
                {t(
                  "The append-only operator action is recorded. This does not confirm ERPNext completion.",
                )}
              </span>
            </div>
          ) : null}
          {command.kind === "failed" ? (
            <Panel
              title={
                command.conflict
                  ? t("Command conflict")
                  : t("Operator action not completed")
              }
            >
              {command.conflict ? (
                <p>
                  {t(
                    "The operation changed before this command committed. Refresh and review the current state before trying again.",
                  )}
                </p>
              ) : null}
              <RequestFailurePanel failure={command.failure} />
            </Panel>
          ) : null}

          <Panel
            actions={
              <div className="table-tools integration-operation-toolbar">
                <label className="integration-operation-filter">
                  <span>{t("Operation")}</span>
                  <Select
                    aria-label={t("Operation")}
                    onChange={(event) => {
                      const operationKind = event.currentTarget.value;
                      selectedIdRef.current = null;
                      setSelectedId(null);
                      setDetail({ kind: "idle" });
                      setResource({ kind: "loading" });
                      setFilters((current) => ({
                        ...current,
                        cursor: undefined,
                        operationKind: operationKind
                          ? (operationKind as IntegrationOperationKind)
                          : undefined,
                      }));
                    }}
                    value={filters.operationKind ?? ""}
                  >
                    <option value="">{t("All operations")}</option>
                    {integrationOperationKinds.map((kind) => (
                      <option key={kind} value={kind}>
                        {operationLabel(t, kind)}
                      </option>
                    ))}
                  </Select>
                </label>
                <label className="integration-operation-filter">
                  <span>{t("Shared state")}</span>
                  <Select
                    aria-label={t("Shared state")}
                    onChange={(event) => {
                      const sharedState = event.currentTarget.value;
                      selectedIdRef.current = null;
                      setSelectedId(null);
                      setDetail({ kind: "idle" });
                      setResource({ kind: "loading" });
                      setFilters((current) => ({
                        ...current,
                        cursor: undefined,
                        sharedState: sharedState
                          ? (sharedState as IntegrationOperationState)
                          : undefined,
                      }));
                    }}
                    value={filters.sharedState ?? ""}
                  >
                    <option value="">{t("All states")}</option>
                    {integrationOperationStates.map((state) => (
                      <option key={state} value={state}>
                        {stateLabel(t, state)}
                      </option>
                    ))}
                  </Select>
                </label>
                <Button
                  aria-pressed={filters.logicalDlq === true}
                  onClick={() => {
                    selectedIdRef.current = null;
                    setSelectedId(null);
                    setDetail({ kind: "idle" });
                    setResource({ kind: "loading" });
                    setFilters((current) => ({
                      ...current,
                      cursor: undefined,
                      logicalDlq: !current.logicalDlq,
                    }));
                  }}
                >
                  {filters.logicalDlq
                    ? t("Show all operations")
                    : t("Show logical DLQ")}
                </Button>
              </div>
            }
            title={t("Project operation worklist")}
          >
            {resource.value.items.length ? (
              <div className="integration-operation-layout">
                <div className="integration-operation-worklist table-scroll">
                  <table className="data-table integration-operation-table">
                    <thead>
                      <tr>
                        <th>{t("Operation")}</th>
                        <th>{t("Owning state")}</th>
                        <th>{t("Shared state")}</th>
                        <th>{t("Updated")}</th>
                        <th>{t("Allowed action")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resource.value.items.map((item) => (
                        <tr
                          aria-selected={selectedId === item.operationGlobalId}
                          className={
                            selectedId === item.operationGlobalId
                              ? "is-selected"
                              : undefined
                          }
                          key={item.operationGlobalId}
                          onClick={() => {
                            if (
                              selectedIdRef.current === item.operationGlobalId
                            )
                              return;
                            selectedIdRef.current = item.operationGlobalId;
                            setSelectedId(item.operationGlobalId);
                            setDetail({
                              kind: "loading",
                              operationId: item.operationGlobalId,
                            });
                            setCommand({ kind: "idle" });
                          }}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              if (
                                selectedIdRef.current === item.operationGlobalId
                              )
                                return;
                              selectedIdRef.current = item.operationGlobalId;
                              setSelectedId(item.operationGlobalId);
                              setDetail({
                                kind: "loading",
                                operationId: item.operationGlobalId,
                              });
                              setCommand({ kind: "idle" });
                            }
                          }}
                          tabIndex={0}
                        >
                          <td className="integration-operation-identity-cell">
                            <strong className="integration-operation-kind">
                              {operationLabel(t, item.operationKind)}
                            </strong>
                            <small
                              className="integration-operation-id"
                              data-language-exempt="identifier"
                            >
                              {item.operationGlobalId}
                            </small>
                          </td>
                          <td
                            className="integration-operation-cell"
                            data-language-exempt="identifier"
                          >
                            {item.rawState}
                          </td>
                          <td className="integration-operation-cell">
                            <SemanticStatus
                              label={stateLabel(t, item.sharedState)}
                              tone={stateTone(item.sharedState)}
                            />
                          </td>
                          <td className="integration-operation-cell">
                            <time dateTime={item.updatedAt}>
                              {formatDateTime(locale, item.updatedAt)}
                            </time>
                          </td>
                          <td className="integration-operation-cell">
                            {availableAction(item) === "replay"
                              ? t("Replay request")
                              : availableAction(item) ===
                                  "request_reconciliation"
                                ? t("Reconciliation request")
                                : t("Observe only")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <aside
                  aria-label={t("Operation inspector")}
                  className="integration-operation-inspector docked-inspector"
                >
                  <Panel
                    bodyClassName="integration-operation-inspector-body"
                    className="integration-operation-inspector-panel"
                    title={t("Operation inspector")}
                  >
                    {detail.kind === "loading" ? (
                      <div aria-busy="true" role="status">
                        {t("Loading operation detail")}
                      </div>
                    ) : null}
                    {detail.kind === "failed" ? (
                      <RequestFailurePanel failure={detail.failure} />
                    ) : null}
                    {selected && action ? (
                      <div className="integration-operation-primary-action">
                        <Button
                          className="integration-operation-primary-button"
                          disabled={!canAct || commandProcessing}
                          onClick={(event) => {
                            actionButtonRef.current = event.currentTarget;
                            setReviewAction(action);
                          }}
                          visual="primary"
                        >
                          {actionLabel(t, action)}
                        </Button>
                      </div>
                    ) : null}
                    {selected && !action ? (
                      <p className="integration-operation-no-action">
                        {t(
                          "This operation is observe-only. Correction or new owning commands remain outside this workspace.",
                        )}
                      </p>
                    ) : null}
                    {detail.kind === "loaded" ? (
                      <DetailInspector detail={detail.value} />
                    ) : null}
                  </Panel>
                </aside>
              </div>
            ) : (
              <div className="workspace-resource-state" role="status">
                <h2>{t("No integration operations")}</h2>
                <p>
                  {filters.logicalDlq
                    ? t(
                        "No operation currently belongs to the Project logical DLQ classification.",
                      )
                    : t(
                        "No Project-contained operation matches the current filters.",
                      )}
                </p>
              </div>
            )}
            <footer className="table-footer">
              <span>
                {t("Showing {{count}} operations", {
                  count: formatNumber(locale, resource.value.items.length, 0),
                })}
              </span>
              <Button
                disabled={!resource.value.nextCursor}
                onClick={() => {
                  if (!resource.value.nextCursor) return;
                  selectedIdRef.current = null;
                  setSelectedId(null);
                  setDetail({ kind: "idle" });
                  setResource({ kind: "loading" });
                  setFilters((current) => ({
                    ...current,
                    cursor: resource.value.nextCursor ?? undefined,
                  }));
                }}
              >
                {t("Next page")}
              </Button>
            </footer>
          </Panel>
        </>
      ) : null}

      {reviewAction && selected ? (
        <ImpactReview
          confirmLabel={
            reviewAction === "replay"
              ? t("Request exact replay")
              : t("Request reconciliation")
          }
          details={actionReviewDetails(t, selected, reviewAction)}
          onCancel={() => {
            setReviewAction(null);
          }}
          onConfirm={requestCommand}
          returnFocusTarget={() => actionButtonRef.current}
          title={
            reviewAction === "replay"
              ? t("Replay impact review")
              : t("Reconciliation impact review")
          }
        />
      ) : null}
    </article>
  );
}
