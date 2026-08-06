import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  EngineeringBomSummaryViewModel,
  EngineeringBomRevisionViewModel,
} from "../api/ebom-data-source";
import type {
  CreateEngineeringBomPublishRequestCommand,
  EngineeringBomPublishRequestDataSource,
  EngineeringBomPublishRequestListViewModel,
  EngineeringBomPublishRequestViewModel,
  PublishFaultKind,
  PublishMappingState,
  PublishNodeOperation,
  PublishNodeState,
  PublishPolicyOptionViewModel,
  PublishRequestState,
  PublishRetryDirective,
} from "../api/publish-request-data-source";
import { PublishRequestCancelledError } from "../api/publish-request-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import {
  formatDateTime,
  formatDecimal,
  formatNumber,
} from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ResourceState<T> =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };

type CommandState =
  | { kind: "idle" }
  | { kind: "processing" }
  | { kind: "accepted"; request: EngineeringBomPublishRequestViewModel }
  | { kind: "failed"; failure: RequestFailure };

function retryable(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function requestStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: PublishRequestState,
): string {
  return state === "validated"
    ? t("Validated in Mock")
    : t("Manual intervention");
}

function nodeStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: PublishNodeState,
): string {
  switch (state) {
    case "validated":
      return t("Validated in Mock");
    case "queued":
      return t("Queued");
    case "processing":
      return t("Processing");
    case "succeeded":
      return t("Target reported success");
    case "failed_retryable":
      return t("Retryable failure");
    case "failed_final":
      return t("Final failure");
    case "uncertain_after_timeout":
      return t("Uncertain after timeout");
    case "blocked_mapping":
      return t("Blocked by mapping");
    case "target_unavailable":
      return t("Target unavailable");
  }
}

function nodeTone(
  state: PublishNodeState,
): "danger" | "info" | "success" | "warning" {
  if (state === "succeeded") return "success";
  if (state === "validated" || state === "queued" || state === "processing")
    return "info";
  if (state === "failed_final") return "danger";
  return "warning";
}

function mappingLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: PublishMappingState,
): string {
  switch (state) {
    case "unmapped":
      return t("Unmapped");
    case "current":
      return t("Current mapping");
    case "stale":
      return t("Stale mapping");
    case "conflict":
      return t("Mapping conflict");
  }
}

function operationLabel(
  t: ReturnType<typeof useI18n>["t"],
  operation: PublishNodeOperation,
): string {
  switch (operation) {
    case "create_item":
      return t("Create Item intent");
    case "update_item_engineering_fields":
      return t("Update engineering fields intent");
    case "create_or_update_mbom":
      return t("Create or update MBOM intent");
  }
}

function faultLabel(
  t: ReturnType<typeof useI18n>["t"],
  fault: PublishFaultKind | null,
): string {
  if (fault === null) return t("None");
  const labels: Record<PublishFaultKind, string> = {
    duplicate_request: t("Duplicate request"),
    payload_conflict: t("Payload conflict"),
    timeout_after_possible_commit: t("Timeout after possible commit"),
    rate_limited: t("Rate limited"),
    target_server_error: t("Target server error"),
    business_validation: t("Business validation failure"),
    partial_node_success: t("Partial node success"),
    stale_mapping: t("Stale mapping"),
    target_unavailable: t("Target unavailable"),
    restart_replay: t("Restart replay"),
  };
  return labels[fault];
}

function retryDirectiveLabel(
  t: ReturnType<typeof useI18n>["t"],
  directive: PublishRetryDirective,
): string {
  const labels: Record<PublishRetryDirective, string> = {
    none: t("No retry action"),
    replay_sealed_response: t("Replay sealed response"),
    reject_payload_conflict: t("Reject payload conflict"),
    reconcile_before_retry: t("Reconcile before retry"),
    retry_after: t("Retry after target delay"),
    retry_same_idempotency: t("Retry with the same idempotency key"),
    manual_correction: t("Manual correction required"),
    retry_failed_nodes_only: t("Retry failed nodes only"),
    resolve_mapping: t("Resolve mapping first"),
    replay_original_request: t("Replay original request"),
  };
  return labels[directive];
}

function policyValue(policy: PublishPolicyOptionViewModel): string {
  return `${policy.globalId}:${String(policy.version)}:${policy.snapshotHash}`;
}

function selectedPolicy(
  policies: readonly PublishPolicyOptionViewModel[],
  value: string,
): PublishPolicyOptionViewModel | null {
  return policies.find((policy) => policyValue(policy) === value) ?? null;
}

function Loading({ label }: { label: string }): React.JSX.Element {
  return (
    <div aria-busy="true" className="publish-request__resource" role="status">
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <span className="visually-hidden">{label}</span>
    </div>
  );
}

function Failure({
  failure,
  onRetry,
}: {
  failure: RequestFailure;
  onRetry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <div className="publish-request__resource" role="alert">
      <SemanticStatus label={t("Error")} tone="danger" />
      <RequestFailurePanel failure={failure} />
      {retryable(failure) ? (
        <Button icon="refresh" onClick={onRetry}>
          {failure.problem?.status === 409 ? t("Reload") : t("Retry")}
        </Button>
      ) : null}
    </div>
  );
}

export function EngineeringBomPublishRequestWorkspace({
  dataSource,
  disabled = false,
  ebom,
  onDirtyChange,
  projectId,
  revision,
}: {
  dataSource?: EngineeringBomPublishRequestDataSource | undefined;
  disabled?: boolean | undefined;
  ebom: EngineeringBomSummaryViewModel;
  onDirtyChange?: ((dirty: boolean) => void) | undefined;
  projectId: string;
  revision: EngineeringBomRevisionViewModel;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [listAttempt, setListAttempt] = useState(0);
  const [detailAttempt, setDetailAttempt] = useState(0);
  const [listState, setListState] = useState<
    ResourceState<EngineeringBomPublishRequestListViewModel>
  >(() => ({
    kind:
      dataSource && revision.lifecycle.state === "released"
        ? "loading"
        : "idle",
  }));
  const [detailState, setDetailState] = useState<
    ResourceState<EngineeringBomPublishRequestViewModel>
  >({ kind: "idle" });
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(
    null,
  );
  const [formOpen, setFormOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [policyRef, setPolicyRef] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [commandState, setCommandState] = useState<CommandState>({
    kind: "idle",
  });
  const idempotencyKey = useRef<string | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const firstControl = useRef<HTMLLabelElement | null>(null);

  const list = listState.kind === "loaded" ? listState.value : null;
  const detail = detailState.kind === "loaded" ? detailState.value : null;
  const selectedSummary = useMemo(
    () =>
      list?.items.find((item) => item.globalId === selectedRequestId) ?? null,
    [list?.items, selectedRequestId],
  );

  useEffect(() => {
    onDirtyChange?.(dirty);
    return () => {
      onDirtyChange?.(false);
    };
  }, [dirty, onDirtyChange]);

  const closeForm = useCallback((): void => {
    setFormOpen(false);
    setDirty(false);
    setFormError(null);
    setReason("");
    setConfirmed(false);
    idempotencyKey.current = null;
    globalThis.queueMicrotask(() => returnFocus.current?.focus());
  }, []);

  useEffect(() => {
    if (!dataSource || revision.lifecycle.state !== "released")
      return undefined;
    const controller = new AbortController();
    // Defer the transport until React StrictMode has completed its probe
    // cleanup, so the read-only request is issued once by the committed effect.
    const startTimer = globalThis.setTimeout(() => {
      if (controller.signal.aborted) return;
      void dataSource
        .loadRequests(
          projectId,
          ebom.globalId,
          revision.globalId,
          controller.signal,
        )
        .then((value) => {
          if (controller.signal.aborted) return;
          setListState({ kind: "loaded", value });
          setPolicyRef(value.policies[0] ? policyValue(value.policies[0]) : "");
          const firstRequestId = value.items[0]?.globalId ?? null;
          setSelectedRequestId(firstRequestId);
          setDetailState({ kind: firstRequestId ? "loading" : "idle" });
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            error instanceof PublishRequestCancelledError
          )
            return;
          setListState({ failure: toRequestFailure(error), kind: "failed" });
        });
    }, 0);
    return () => {
      globalThis.clearTimeout(startTimer);
      controller.abort();
    };
  }, [
    dataSource,
    ebom.globalId,
    listAttempt,
    projectId,
    revision.globalId,
    revision.lifecycle.state,
  ]);

  useEffect(() => {
    if (
      !dataSource ||
      !selectedRequestId ||
      revision.lifecycle.state !== "released"
    )
      return undefined;
    const controller = new AbortController();
    void dataSource
      .loadRequest(
        projectId,
        ebom.globalId,
        revision.globalId,
        selectedRequestId,
        controller.signal,
      )
      .then((value) => {
        if (!controller.signal.aborted)
          setDetailState({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof PublishRequestCancelledError
        )
          return;
        setDetailState({ failure: toRequestFailure(error), kind: "failed" });
      });
    return () => {
      controller.abort();
    };
  }, [
    dataSource,
    detailAttempt,
    ebom.globalId,
    projectId,
    revision.globalId,
    revision.lifecycle.state,
    selectedRequestId,
  ]);

  const reload = useCallback((): void => {
    closeForm();
    setCommandState({ kind: "idle" });
    setSelectedRequestId(null);
    setDetailState({ kind: "idle" });
    setListState({ kind: "loading" });
    setListAttempt((current) => current + 1);
  }, [closeForm]);

  const openForm = (trigger: HTMLElement): void => {
    if (!list) return;
    returnFocus.current = trigger;
    setPolicyRef(list.policies[0] ? policyValue(list.policies[0]) : "");
    setReason("");
    setConfirmed(false);
    setDirty(false);
    setFormError(null);
    idempotencyKey.current = `ebom-publish-${globalThis.crypto.randomUUID()}`;
    setFormOpen(true);
    globalThis.queueMicrotask(() =>
      firstControl.current?.querySelector("select")?.focus(),
    );
  };

  const submit = (): void => {
    if (!dataSource || !list || !sessionCommandContext) return;
    const policy = selectedPolicy(list.policies, policyRef);
    if (!policy || !confirmed || !reason.trim()) {
      setFormError(
        t(
          "Select the exact publish policy, enter a reason and confirm Mock validation before continuing.",
        ),
      );
      return;
    }
    const key =
      idempotencyKey.current ??
      `ebom-publish-${globalThis.crypto.randomUUID()}`;
    idempotencyKey.current = key;
    const command: CreateEngineeringBomPublishRequestCommand = {
      expectedEbomVersion: ebom.optimisticVersion,
      expectedRevisionSnapshotHash: revision.snapshotHash,
      expectedLifecycleVersion: revision.lifecycle.version,
      publishPolicyGlobalId: policy.globalId,
      publishPolicyVersion: policy.version,
      publishPolicySnapshotHash: policy.snapshotHash,
      targetMode: "mock",
      confirmed: true,
      confirmationIntent: "validate_exact_released_ebom_for_item_mbom_publish",
      reason,
    };
    const controller = new AbortController();
    setCommandState({ kind: "processing" });
    setFormError(null);
    void dataSource
      .createRequest(projectId, ebom.globalId, revision.globalId, command, {
        ...sessionCommandContext,
        idempotencyKey: key,
        signal: controller.signal,
      })
      .then((request) => {
        setCommandState({ kind: "accepted", request });
        setSelectedRequestId(request.globalId);
        setListState((current) => {
          if (current.kind !== "loaded") return current;
          const items = current.value.items.some(
            (item) => item.globalId === request.globalId,
          )
            ? current.value.items.map((item) =>
                item.globalId === request.globalId ? request : item,
              )
            : [request, ...current.value.items];
          return { kind: "loaded", value: { ...current.value, items } };
        });
        setDetailState({ kind: "loaded", value: request });
        closeForm();
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof PublishRequestCancelledError
        )
          return;
        setCommandState({ failure: toRequestFailure(error), kind: "failed" });
      });
  };

  if (revision.lifecycle.state !== "released") {
    return (
      <Panel title={t("Formal publish requests")}>
        <div
          className="scenario-banner scenario-banner--read_only"
          role="status"
        >
          <SemanticStatus label={t("Released revision required")} tone="info" />
          <span>
            {t(
              "Release this exact EBOM revision before preparing a formal Item and MBOM publish request.",
            )}
          </span>
        </div>
      </Panel>
    );
  }

  if (!dataSource) {
    return (
      <Panel title={t("Formal publish requests")}>
        <div className="scenario-banner scenario-banner--partial" role="status">
          <SemanticStatus label={t("Unavailable")} tone="warning" />
          <span>
            {t(
              "The publish-request data source is not configured. No target system was contacted.",
            )}
          </span>
        </div>
      </Panel>
    );
  }

  return (
    <Panel scrollableBody title={t("Formal publish requests")}>
      <section
        aria-label={t("EBOM publish-request workspace")}
        className="publish-request"
      >
        <div className="scenario-banner scenario-banner--partial" role="status">
          <SemanticStatus label={t("Mock validation only")} tone="info" />
          <span>
            {t(
              "Validated means the frozen NPI request passed local checks. It was not queued, sent or completed in ERPNext.",
            )}
          </span>
        </div>
        {listState.kind === "loading" || listState.kind === "idle" ? (
          <Loading label={t("Loading formal publish requests")} />
        ) : listState.kind === "failed" ? (
          <Failure failure={listState.failure} onRetry={reload} />
        ) : (
          <>
            <div className="publish-request__toolbar">
              <span>
                {t("Requests")}:{" "}
                {formatNumber(locale, listState.value.items.length, 0)}
              </span>
              <div className="detail-actions">
                <Button
                  disabled={
                    disabled ||
                    formOpen ||
                    commandState.kind === "processing" ||
                    !listState.value.permissions.create ||
                    listState.value.policies.length === 0 ||
                    sessionCommandContext === null
                  }
                  onClick={(event) => {
                    openForm(event.currentTarget);
                  }}
                  visual={formOpen ? "secondary" : "primary"}
                >
                  {t("Prepare publish request")}
                </Button>
                <Button
                  disabled={commandState.kind === "processing"}
                  icon="refresh"
                  onClick={reload}
                >
                  {t("Reload")}
                </Button>
              </div>
            </div>

            {!listState.value.permissions.create ? (
              <div
                className="scenario-banner scenario-banner--read_only"
                role="status"
              >
                <SemanticStatus label={t("Read only")} tone="info" />
                <span>
                  {t(
                    "You can inspect exact publish evidence but cannot prepare a new request.",
                  )}
                </span>
              </div>
            ) : null}
            {listState.value.policies.length === 0 ? (
              <div
                className="scenario-banner scenario-banner--partial"
                role="status"
              >
                <SemanticStatus
                  label={t("Publish authority unavailable")}
                  tone="warning"
                />
                <span>
                  {t(
                    "No exact published Mock policy grants you permission to prepare this request.",
                  )}
                </span>
              </div>
            ) : null}

            {commandState.kind === "processing" ? (
              <div className="publish-request__command" role="status">
                <SemanticStatus label={t("Processing")} tone="info" />
                <span>
                  {t("Validating the exact released EBOM in Mock mode")}
                </span>
              </div>
            ) : commandState.kind === "failed" ? (
              <div className="publish-request__command" role="alert">
                <SemanticStatus label={t("Command failed")} tone="danger" />
                <RequestFailurePanel failure={commandState.failure} />
                {retryable(commandState.failure) ? (
                  <Button
                    icon="refresh"
                    onClick={
                      commandState.failure.problem?.status === 409
                        ? reload
                        : submit
                    }
                  >
                    {commandState.failure.problem?.status === 409
                      ? t("Reload")
                      : t("Retry")}
                  </Button>
                ) : null}
              </div>
            ) : commandState.kind === "accepted" ? (
              <div className="publish-request__command" role="status">
                <SemanticStatus label={t("Validated in Mock")} tone="info" />
                <span>
                  {t(
                    "The immutable request was recorded locally. ERPNext was not contacted.",
                  )}
                </span>
              </div>
            ) : null}

            {formOpen ? (
              <form
                className="publish-request__form"
                onSubmit={(event) => {
                  event.preventDefault();
                  submit();
                }}
              >
                <div className="publish-request__form-evidence">
                  <SemanticStatus
                    label={t("Exact released input")}
                    tone="info"
                  />
                  <DefinitionList
                    rows={[
                      {
                        label: t("Revision"),
                        value: `R${String(revision.revisionNumber)}`,
                        exempt: "identifier",
                      },
                      {
                        label: t("Lines"),
                        value: formatNumber(locale, revision.lines.length, 0),
                      },
                      {
                        label: t("EBOM version"),
                        value: formatNumber(locale, ebom.optimisticVersion, 0),
                      },
                      {
                        label: t("Lifecycle version"),
                        value: formatNumber(
                          locale,
                          revision.lifecycle.version,
                          0,
                        ),
                      },
                      {
                        label: t("Snapshot hash"),
                        value: revision.snapshotHash,
                        exempt: "identifier",
                      },
                      { label: t("Target mode"), value: t("Mock only") },
                    ]}
                  />
                </div>
                <label ref={firstControl}>
                  <span>{t("Exact publish policy")}</span>
                  <Select
                    onChange={(event) => {
                      setPolicyRef(event.currentTarget.value);
                      setDirty(true);
                    }}
                    required
                    value={policyRef}
                  >
                    {listState.value.policies.map((policy) => (
                      <option
                        data-language-exempt="business-data"
                        key={policyValue(policy)}
                        value={policyValue(policy)}
                      >
                        {policy.title} · v{String(policy.version)} · Mock
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("Reason")}</span>
                  <TextInput
                    maxLength={280}
                    onChange={(event) => {
                      setReason(event.currentTarget.value);
                      setDirty(true);
                    }}
                    required
                    value={reason}
                  />
                </label>
                <label className="confirmation-check publish-request__form-wide">
                  <input
                    checked={confirmed}
                    onChange={(event) => {
                      setConfirmed(event.currentTarget.checked);
                      setDirty(true);
                    }}
                    type="checkbox"
                  />
                  <span>
                    {t(
                      "I confirm validation of this exact released EBOM in Mock mode. No Item or MBOM will be created in ERPNext.",
                    )}
                  </span>
                </label>
                {formError ? (
                  <p
                    className="form-error publish-request__form-wide"
                    role="alert"
                  >
                    {formError}
                  </p>
                ) : null}
                <div className="detail-actions publish-request__form-wide">
                  <Button
                    disabled={commandState.kind === "processing"}
                    type="submit"
                    visual="primary"
                  >
                    {t("Validate exact released EBOM")}
                  </Button>
                  <Button
                    disabled={commandState.kind === "processing"}
                    onClick={closeForm}
                    type="button"
                  >
                    {t("Cancel")}
                  </Button>
                </div>
              </form>
            ) : null}

            {listState.value.items.length === 0 ? (
              <div className="publish-request__empty" role="status">
                <SemanticStatus label={t("No publish request")} tone="info" />
                <p>
                  {t(
                    "No immutable Mock validation request has been recorded for this exact revision.",
                  )}
                </p>
              </div>
            ) : (
              <div className="publish-request__layout">
                <div className="publish-request__list">
                  <table className="data-table data-table--compact">
                    <thead>
                      <tr>
                        <th>{t("Request")}</th>
                        <th>{t("State")}</th>
                        <th>{t("Nodes")}</th>
                        <th>{t("Created")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {listState.value.items.map((request) => (
                        <tr
                          aria-selected={request.globalId === selectedRequestId}
                          className={
                            request.globalId === selectedRequestId
                              ? "is-selected"
                              : undefined
                          }
                          key={request.globalId}
                        >
                          <td>
                            <button
                              className="table-link"
                              data-language-exempt="identifier"
                              onClick={() => {
                                setDetailState({ kind: "loading" });
                                setSelectedRequestId(request.globalId);
                              }}
                              type="button"
                            >
                              {request.globalId}
                            </button>
                          </td>
                          <td>
                            <SemanticStatus
                              label={requestStateLabel(t, request.state)}
                              tone={
                                request.state === "validated"
                                  ? "info"
                                  : "warning"
                              }
                            />
                          </td>
                          <td>
                            {formatNumber(locale, request.nodes.length, 0)}
                          </td>
                          <td>{formatDateTime(locale, request.createdAt)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {detailState.kind === "loading" ? (
                  <Loading
                    label={t("Loading exact publish-request evidence")}
                  />
                ) : detailState.kind === "failed" ? (
                  <Failure
                    failure={detailState.failure}
                    onRetry={() => {
                      setDetailState({ kind: "loading" });
                      setDetailAttempt((current) => current + 1);
                    }}
                  />
                ) : detail ? (
                  <div className="publish-request__detail">
                    <div className="publish-request__detail-header">
                      <SemanticStatus
                        label={requestStateLabel(t, detail.state)}
                        tone={detail.state === "validated" ? "info" : "warning"}
                      />
                      <span>
                        {t("Target mode")}: {t("Mock only")}
                      </span>
                      <span>
                        {t("Dispatch")}: {t("Disabled")}
                      </span>
                    </div>
                    <DefinitionList
                      rows={[
                        {
                          label: t("Request ID"),
                          value: detail.globalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Actor"),
                          value: detail.actorUserId,
                          exempt: "business-data",
                        },
                        {
                          label: t("Released"),
                          value: formatDateTime(
                            locale,
                            detail.releasedEbom.releasedAt,
                          ),
                        },
                        {
                          label: t("Release event"),
                          value: detail.releasedEbom.releaseEventGlobalId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Publish policy version"),
                          value: formatNumber(locale, detail.policy.version, 0),
                        },
                        {
                          label: t("Payload hash"),
                          value: detail.payloadHash,
                          exempt: "identifier",
                        },
                        {
                          label: t("Trace ID"),
                          value: detail.traceId,
                          exempt: "identifier",
                        },
                        {
                          label: t("Formal target identifiers"),
                          value: t("Not assigned"),
                        },
                      ]}
                    />
                    <div
                      aria-label={t("Publish-request node results")}
                      className="publish-request__nodes"
                      tabIndex={0}
                    >
                      <table className="data-table data-table--compact">
                        <thead>
                          <tr>
                            <th>{t("Line")}</th>
                            <th>{t("Engineering item")}</th>
                            <th>{t("Quantity")}</th>
                            <th>{t("Requested operations")}</th>
                            <th>{t("Mapping")}</th>
                            <th>{t("Result")}</th>
                            <th>{t("Fault")}</th>
                            <th>{t("Future recovery")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.nodes.map((node) => {
                            const result =
                              node.results[node.results.length - 1];
                            return (
                              <tr key={node.globalId}>
                                <td data-language-exempt="identifier">
                                  {node.line.lineKey}
                                </td>
                                <td>
                                  <span
                                    className="publish-request__node-meta"
                                    data-language-exempt="identifier"
                                  >
                                    {node.line.engineeringItemId}
                                  </span>
                                  <small
                                    className="publish-request__node-meta"
                                    data-language-exempt="business-data"
                                  >
                                    {node.line.description}
                                  </small>
                                </td>
                                <td>
                                  {formatDecimal(locale, node.line.quantity)}{" "}
                                  <span data-language-exempt="unit">
                                    {node.line.engineeringUom}
                                  </span>
                                </td>
                                <td>
                                  {node.operations
                                    .map((operation) =>
                                      operationLabel(t, operation),
                                    )
                                    .join("; ")}
                                </td>
                                <td>
                                  <SemanticStatus
                                    label={mappingLabel(t, node.mapping.state)}
                                    tone={
                                      node.mapping.state === "unmapped" ||
                                      node.mapping.state === "current"
                                        ? "info"
                                        : "warning"
                                    }
                                  />
                                  <small className="publish-request__node-meta">
                                    {t("Formal target identifiers")}:{" "}
                                    {t("Not assigned")}
                                  </small>
                                </td>
                                <td>
                                  <SemanticStatus
                                    label={nodeStateLabel(t, node.resultState)}
                                    tone={nodeTone(node.resultState)}
                                  />
                                </td>
                                <td>
                                  {faultLabel(t, result?.faultKind ?? null)}
                                </td>
                                <td>
                                  {result
                                    ? retryDirectiveLabel(
                                        t,
                                        result.futureRetryDirective,
                                      )
                                    : t("No retry action")}
                                  {result?.reconciliationRequired ? (
                                    <small className="publish-request__node-meta">
                                      {t("Reconciliation required")}
                                    </small>
                                  ) : null}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : selectedSummary ? null : (
                  <div className="publish-request__empty" role="status">
                    <p>
                      {t(
                        "Select an immutable request to inspect its exact evidence.",
                      )}
                    </p>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </section>
    </Panel>
  );
}
