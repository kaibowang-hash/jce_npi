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
import type {
  ItemPublishDataSource,
  ItemPublishRequestDetailViewModel,
  ItemPublishRequestListViewModel,
  ItemPublishRequestState,
  ItemPublishTargetMode,
} from "../api/item-publish-data-source";
import {
  ITEM_PUBLISH_ACKNOWLEDGEMENT,
  ItemPublishCancelledError,
} from "../api/item-publish-data-source";
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
import {
  Button,
  CompactAction,
  Select,
  TextInput,
} from "../ui-adapters/npi-ui";

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

type ItemCommandState =
  | { kind: "idle" }
  | { kind: "processing" }
  | { kind: "accepted"; detail: ItemPublishRequestDetailViewModel }
  | { kind: "failed"; failure: RequestFailure };

function itemStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: ItemPublishRequestState,
): string {
  const labels: Record<ItemPublishRequestState, string> = {
    validated_mock: t("Validated in Mock; not dispatched"),
    queued: t("Queued; target result pending"),
    processing: t("Processing; target result pending"),
    synthetic_verified: t("Synthetic verification; not authoritative"),
    succeeded: t("Authoritative Sandbox result observed"),
    failed_retryable: t("Retryable failure; no success recorded"),
    failed_final: t("Final failure; no success recorded"),
    uncertain_after_timeout: t(
      "Uncertain after timeout; reconciliation required",
    ),
    mapping_conflict: t("Mapping conflict; no mapping changed"),
  };
  return labels[state];
}

function itemAttemptStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: string,
): string {
  switch (state) {
    case "started":
      return t("Started");
    case "synthetic_verified":
      return t("Synthetic verification");
    case "observed_success":
      return t("Observed success");
    case "observed_failure":
      return t("Observed failure");
    case "uncertain":
      return t("Uncertain");
    default:
      return t("Unknown attempt state");
  }
}

function itemFaultKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  fault: string | null,
): string {
  switch (fault) {
    case null:
      return t("None");
    case "none":
      return t("None");
    case "payload_conflict":
      return t("Payload conflict");
    case "source_engineering_item_conflict":
      return t("Source engineering Item conflict");
    case "stale_mapping":
      return t("Stale mapping");
    case "timeout_after_possible_commit":
      return t("Timeout after possible commit");
    case "rate_limited":
      return t("Rate limited");
    case "target_server_error":
      return t("Target server error");
    case "business_validation":
      return t("Business validation failure");
    case "response_contract_invalid":
      return t("Response contract invalid");
    case "response_authentication_invalid":
      return t("Response authentication invalid");
    case "target_unavailable":
      return t("Target unavailable");
    default:
      return t("Unknown execution fault");
  }
}

function itemStateTone(
  state: ItemPublishRequestState,
): "danger" | "info" | "success" | "warning" {
  if (state === "succeeded") return "success";
  if (state === "failed_final") return "danger";
  if (
    state === "failed_retryable" ||
    state === "uncertain_after_timeout" ||
    state === "mapping_conflict"
  )
    return "warning";
  return "info";
}

function targetModeLabel(
  t: ReturnType<typeof useI18n>["t"],
  mode: ItemPublishTargetMode,
): string {
  if (mode === "mock") return t("Mock validation");
  if (mode === "synthetic") return t("Disposable synthetic runtime");
  return t("Sandbox execution");
}

function itemActionBlockReason(
  t: ReturnType<typeof useI18n>["t"],
  list: ItemPublishRequestListViewModel,
  sessionAvailable: boolean,
  disabled: boolean,
): string | null {
  if (disabled) return t("Another EBOM command is in progress.");
  if (!list.permissions.canView)
    return t("You cannot view Item execution history for this Project.");
  if (!list.permissions.canExecute)
    return t("You can inspect Item execution but cannot request it.");
  if (!list.executionProfile)
    return t("The exact Item execution profile is unavailable.");
  if (!list.mappingExpectation)
    return t("The current Item mapping expectation is unavailable.");
  if (list.executionProfile.targetMode === "mock")
    return t("Mock validates the request locally and cannot execute an Item.");
  const existing = list.items[0];
  if (existing) {
    if (existing.state === "uncertain_after_timeout")
      return t(
        "The outcome is uncertain. Reconciliation is required before any new request.",
      );
    if (existing.state === "mapping_conflict")
      return t("Resolve the mapping conflict before any new request.");
    if (existing.state === "queued" || existing.state === "processing")
      return t("The existing Item request is still in flight.");
    return t("An immutable Item request already exists for this exact source.");
  }
  if (!sessionAvailable) return t("The secure command session is unavailable.");
  return null;
}

function ItemPublishExecutionInspector({
  active,
  dataSource,
  disabled,
  onDirtyChange,
  projectId,
  publishRequest,
}: {
  active: boolean;
  dataSource?: ItemPublishDataSource | undefined;
  disabled: boolean;
  onDirtyChange: (dirty: boolean) => void;
  projectId: string;
  publishRequest: EngineeringBomPublishRequestViewModel;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const inspectorRef = useRef<HTMLElement | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [reloadAttempt, setReloadAttempt] = useState(0);
  const [listState, setItemListState] = useState<
    ResourceState<ItemPublishRequestListViewModel>
  >({ kind: "idle" });
  const [detailState, setItemDetailState] = useState<
    ResourceState<ItemPublishRequestDetailViewModel>
  >({ kind: "idle" });
  const [acknowledged, setAcknowledged] = useState(false);
  const [commandState, setItemCommandState] = useState<ItemCommandState>({
    kind: "idle",
  });
  const idempotencyKey = useRef<string | null>(null);

  const selectedNode =
    publishRequest.nodes.find((node) => node.globalId === selectedNodeId) ??
    null;
  const list = listState.kind === "loaded" ? listState.value : null;
  const detail = detailState.kind === "loaded" ? detailState.value : null;
  const effectiveMappingExpectation =
    detail?.request.mappingExpectation ?? list?.mappingExpectation ?? null;
  const actionBlockReason = list
    ? itemActionBlockReason(t, list, sessionCommandContext !== null, disabled)
    : t("Load the exact Item execution context before requesting execution.");

  useEffect(() => {
    const root = inspectorRef.current;
    if (root) (root as HTMLElement & { inert: boolean }).inert = !active;
  }, [active]);

  useEffect(() => {
    onDirtyChange(acknowledged);
    return () => {
      onDirtyChange(false);
    };
  }, [acknowledged, onDirtyChange]);

  useEffect(() => {
    if (!dataSource || !selectedNode) return undefined;
    const controller = new AbortController();
    const timer = globalThis.setTimeout(() => {
      if (controller.signal.aborted) return;
      void dataSource
        .loadRequests(
          projectId,
          publishRequest.globalId,
          selectedNode.globalId,
          controller.signal,
        )
        .then((value) => {
          if (controller.signal.aborted) return;
          setItemListState({ kind: "loaded", value });
          if (!value.permissions.canView) return;
          const requestId = value.items[0]?.globalId;
          if (!requestId) return;
          setItemDetailState({ kind: "loading" });
          return dataSource.loadRequest(
            projectId,
            requestId,
            controller.signal,
          );
        })
        .then((value) => {
          if (value && !controller.signal.aborted)
            setItemDetailState({ kind: "loaded", value });
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            error instanceof ItemPublishCancelledError
          )
            return;
          const failure = toRequestFailure(error);
          setItemListState((current) =>
            current.kind === "loading" ? { kind: "failed", failure } : current,
          );
          setItemDetailState((current) =>
            current.kind === "loading" ? { kind: "failed", failure } : current,
          );
        });
    }, 0);
    return () => {
      globalThis.clearTimeout(timer);
      controller.abort();
    };
  }, [
    dataSource,
    projectId,
    publishRequest.globalId,
    reloadAttempt,
    selectedNode,
  ]);

  const reload = (): void => {
    setItemListState({ kind: "loading" });
    setItemDetailState({ kind: "idle" });
    setItemCommandState({ kind: "idle" });
    setAcknowledged(false);
    idempotencyKey.current = null;
    setReloadAttempt((current) => current + 1);
  };

  const selectSourceNode = (nodeId: string): void => {
    setItemListState({ kind: "loading" });
    setItemDetailState({ kind: "idle" });
    setItemCommandState({ kind: "idle" });
    setAcknowledged(false);
    idempotencyKey.current = null;
    setSelectedNodeId(nodeId);
  };

  const submit = (): void => {
    if (
      !dataSource ||
      !selectedNode ||
      !list ||
      !sessionCommandContext ||
      actionBlockReason ||
      !acknowledged
    )
      return;
    const mappingExpectation = list.mappingExpectation;
    if (!mappingExpectation) return;
    const key =
      idempotencyKey.current ??
      `item-publish-${globalThis.crypto.randomUUID()}`;
    idempotencyKey.current = key;
    const controller = new AbortController();
    setItemCommandState({ kind: "processing" });
    void dataSource
      .createRequest(
        projectId,
        {
          publishRequestGlobalId: publishRequest.globalId,
          selectedPublishNodeGlobalId: selectedNode.globalId,
          expectedMappingVersion: mappingExpectation.mappingVersion,
          acknowledgement: ITEM_PUBLISH_ACKNOWLEDGEMENT,
        },
        {
          ...sessionCommandContext,
          idempotencyKey: key,
          signal: controller.signal,
        },
      )
      .then((value) => {
        setItemCommandState({ detail: value, kind: "accepted" });
        setItemDetailState({ kind: "loaded", value });
        setItemListState((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  items: [value.request, ...current.value.items],
                },
              }
            : current,
        );
        setAcknowledged(false);
      })
      .catch((error: unknown) => {
        if (error instanceof ItemPublishCancelledError) return;
        setItemCommandState({
          failure: toRequestFailure(error),
          kind: "failed",
        });
      });
  };

  return (
    <section
      aria-hidden={!active}
      aria-label={t("Item execution inspector")}
      className="item-publish"
      ref={inspectorRef}
      style={active ? undefined : { opacity: 0, pointerEvents: "none" }}
    >
      <div className="item-publish__header">
        <div className="item-publish__heading-copy">
          <h3>{t("Item execution inspector")}</h3>
          <p>
            {t(
              "Request and result history is bound to the selected immutable Phase 5 node. Formal Item identity is shown only from the current authoritative mapping.",
            )}
          </p>
        </div>
        <CompactAction
          disabled={commandState.kind === "processing"}
          icon="refresh"
          intent="familiar-low-risk"
          label={t("Reload")}
          onClick={reload}
        />
      </div>

      <div
        aria-label={t("Select exact Item source")}
        className="item-publish__source-list"
        tabIndex={0}
      >
        <table className="data-table data-table--compact">
          <thead>
            <tr>
              <th>{t("Engineering item")}</th>
              <th>{t("Description")}</th>
              <th>{t("Source node")}</th>
              <th>{t("Input hash")}</th>
            </tr>
          </thead>
          <tbody>
            {publishRequest.nodes.map((node) => (
              <tr
                aria-selected={node.globalId === selectedNode?.globalId}
                className={
                  node.globalId === selectedNode?.globalId
                    ? "is-selected"
                    : undefined
                }
                key={node.globalId}
              >
                <td>
                  <button
                    className="table-link"
                    data-language-exempt="identifier"
                    onClick={() => {
                      selectSourceNode(node.globalId);
                    }}
                    type="button"
                  >
                    {node.line.engineeringItemId}
                  </button>
                </td>
                <td data-language-exempt="business-data">
                  {node.line.description}
                </td>
                <td data-language-exempt="identifier">{node.globalId}</td>
                <td data-language-exempt="identifier">{node.inputHash}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!dataSource ? (
        <div className="scenario-banner scenario-banner--partial" role="status">
          <SemanticStatus label={t("Unavailable")} tone="warning" />
          <span>
            {t(
              "The Item execution data source is not configured. No target system was contacted.",
            )}
          </span>
        </div>
      ) : listState.kind === "loading" || listState.kind === "idle" ? (
        <Loading label={t("Loading Item execution context")} />
      ) : listState.kind === "failed" ? (
        <div className="item-publish__resource" role="alert">
          <SemanticStatus
            label={
              listState.failure.problem?.status === 403
                ? t("No permission")
                : t("Item execution unavailable")
            }
            tone="danger"
          />
          <RequestFailurePanel failure={listState.failure} />
          {retryable(listState.failure) ? (
            <Button icon="refresh" onClick={reload}>
              {t("Reload")}
            </Button>
          ) : null}
        </div>
      ) : (
        <>
          <div className="item-publish__status-strip">
            <SemanticStatus
              label={
                detail
                  ? itemStateLabel(t, detail.request.state)
                  : t("No Item execution request")
              }
              tone={detail ? itemStateTone(detail.request.state) : "info"}
            />
            <span>
              {t("Requests")}:{" "}
              {formatNumber(locale, listState.value.items.length, 0)}
            </span>
            <span>
              {t("Execution profile")}:{" "}
              {listState.value.executionProfile
                ? targetModeLabel(
                    t,
                    listState.value.executionProfile.targetMode,
                  )
                : t("Unavailable")}
            </span>
          </div>

          {!listState.value.permissions.canView ? (
            <div
              className="scenario-banner scenario-banner--read_only"
              role="status"
            >
              <SemanticStatus label={t("No permission")} tone="warning" />
              <span>
                {t("You cannot view Item execution history for this Project.")}
              </span>
            </div>
          ) : null}

          <div className="item-publish__grid">
            <div className="item-publish__evidence">
              <h4>{t("Exact source and execution expectation")}</h4>
              <DefinitionList
                rows={[
                  {
                    label: t("Engineering item"),
                    value:
                      detail?.request.source.engineeringItemId ??
                      selectedNode?.line.engineeringItemId ??
                      t("Unavailable"),
                    exempt: "identifier",
                  },
                  {
                    label: t("Source occurrences"),
                    value: formatNumber(
                      locale,
                      detail?.request.source.occurrences.length ??
                        publishRequest.nodes.filter(
                          (node) =>
                            node.line.engineeringItemId ===
                            selectedNode?.line.engineeringItemId,
                        ).length,
                      0,
                    ),
                  },
                  {
                    label: t("Item intent"),
                    value:
                      detail?.request.intent ===
                      "update_item_engineering_fields"
                        ? t("Update engineering fields intent")
                        : t("Create Item intent"),
                  },
                  {
                    label: t("Expected mapping version"),
                    value: effectiveMappingExpectation
                      ? formatNumber(
                          locale,
                          effectiveMappingExpectation.mappingVersion,
                          0,
                        )
                      : t("Unavailable"),
                  },
                  {
                    label: t("Expected target version"),
                    value:
                      effectiveMappingExpectation?.targetVersion ??
                      t("Not assigned"),
                    ...(effectiveMappingExpectation?.targetVersion
                      ? ({ exempt: "identifier" } as const)
                      : {}),
                  },
                  {
                    label: t("Source hash"),
                    value:
                      detail?.request.source.sourceHash ??
                      selectedNode?.inputHash ??
                      t("Unavailable"),
                    exempt: "identifier",
                  },
                  {
                    label: t("Phase 5 request hash"),
                    value: publishRequest.payloadHash,
                    exempt: "identifier",
                  },
                ]}
              />
            </div>
            <div className="item-publish__evidence">
              <h4>{t("Profile and mapping authority")}</h4>
              <DefinitionList
                rows={[
                  {
                    label: t("Profile"),
                    value:
                      detail?.request.profile.profileId ??
                      listState.value.executionProfile?.profileId ??
                      t("Unavailable"),
                    ...(detail?.request.profile.profileId ||
                    listState.value.executionProfile?.profileId
                      ? ({ exempt: "identifier" } as const)
                      : {}),
                  },
                  {
                    label: t("Profile version"),
                    value: listState.value.executionProfile
                      ? formatNumber(
                          locale,
                          listState.value.executionProfile.profileVersion,
                          0,
                        )
                      : t("Unavailable"),
                  },
                  {
                    label: t("Environment"),
                    value:
                      detail?.request.profile.environmentCode ??
                      listState.value.executionProfile?.environmentCode ??
                      t("Unavailable"),
                    exempt: "identifier",
                  },
                  {
                    label: t("Current mapping authority"),
                    value: detail?.currentMapping
                      ? t("Authoritative Sandbox observation")
                      : t("No authoritative mapping"),
                  },
                  {
                    label: t("Formal Item Code"),
                    value:
                      detail?.permissions.canView && detail.currentMapping
                        ? detail.currentMapping.formalItemCode
                        : t("Not assigned"),
                    ...(detail?.permissions.canView && detail.currentMapping
                      ? ({ exempt: "identifier" } as const)
                      : {}),
                  },
                  {
                    label: t("Target version"),
                    value:
                      detail?.permissions.canView && detail.currentMapping
                        ? detail.currentMapping.targetVersion
                        : t("Not assigned"),
                    ...(detail?.permissions.canView && detail.currentMapping
                      ? ({ exempt: "identifier" } as const)
                      : {}),
                  },
                  {
                    label: t("Mapping version"),
                    value: detail?.currentMapping
                      ? formatNumber(
                          locale,
                          detail.currentMapping.mappingVersion,
                          0,
                        )
                      : t("Not assigned"),
                  },
                ]}
              />
            </div>
          </div>

          {detailState.kind === "loading" ? (
            <Loading label={t("Loading Item attempt history")} />
          ) : detailState.kind === "failed" ? (
            <div className="item-publish__resource" role="alert">
              <SemanticStatus
                label={t("Item detail unavailable")}
                tone="danger"
              />
              <RequestFailurePanel failure={detailState.failure} />
              <Button icon="refresh" onClick={reload}>
                {t("Reload")}
              </Button>
            </div>
          ) : detail ? (
            <div className="item-publish__attempts">
              <h4>{t("Immutable attempt history")}</h4>
              {detail.attempts.length === 0 ? (
                <p>{t("No adapter attempt was recorded for this request.")}</p>
              ) : (
                <div className="item-publish__attempt-table" tabIndex={0}>
                  <table className="data-table data-table--compact">
                    <thead>
                      <tr>
                        <th>{t("Attempt")}</th>
                        <th>{t("State")}</th>
                        <th>{t("Adapter boundary")}</th>
                        <th>{t("Started")}</th>
                        <th>{t("Finished")}</th>
                        <th>{t("Fault")}</th>
                        <th>{t("Reconciliation")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.attempts.map((attempt) => (
                        <tr key={attempt.globalId}>
                          <td>
                            {formatNumber(locale, attempt.attemptNumber, 0)}
                          </td>
                          <td>{itemAttemptStateLabel(t, attempt.state)}</td>
                          <td>
                            {attempt.adapterBoundaryCrossed
                              ? t("Crossed")
                              : t("Not crossed")}
                          </td>
                          <td>{formatDateTime(locale, attempt.startedAt)}</td>
                          <td>
                            {attempt.finishedAt
                              ? formatDateTime(locale, attempt.finishedAt)
                              : t("Pending")}
                          </td>
                          <td>{itemFaultKindLabel(t, attempt.faultKind)}</td>
                          <td>
                            {attempt.reconciliationRequired
                              ? t("Required")
                              : t("Not required")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}

          {commandState.kind === "processing" ? (
            <div className="item-publish__command" role="status">
              <SemanticStatus
                label={t("Creating local execution request")}
                tone="info"
              />
              <span>
                {t(
                  "No target success is reported while the request is being committed.",
                )}
              </span>
            </div>
          ) : commandState.kind === "failed" ? (
            <div className="item-publish__command" role="alert">
              <SemanticStatus label={t("Item request failed")} tone="danger" />
              <RequestFailurePanel failure={commandState.failure} />
            </div>
          ) : commandState.kind === "accepted" ? (
            <div className="item-publish__command" role="status">
              <SemanticStatus
                label={itemStateLabel(t, commandState.detail.request.state)}
                tone={itemStateTone(commandState.detail.request.state)}
              />
              <span>
                {t(
                  "The immutable request was committed locally. This is not target success.",
                )}
              </span>
            </div>
          ) : null}

          <form
            className="item-publish__request-form"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <div className="item-publish__request-copy">
              <h4>{t("Request exact Item execution")}</h4>
              <p>
                {t(
                  "Impact: the server freezes this released source, current profile and mapping expectation, then commits an auditable request before any worker may cross an adapter boundary.",
                )}
              </p>
              {actionBlockReason ? (
                <p className="form-error" role="status">
                  {actionBlockReason}
                </p>
              ) : null}
            </div>
            <label className="confirmation-check">
              <input
                checked={acknowledged}
                disabled={
                  Boolean(actionBlockReason) ||
                  commandState.kind === "processing"
                }
                onChange={(event) => {
                  setAcknowledged(event.currentTarget.checked);
                }}
                type="checkbox"
              />
              <span>
                {t(
                  "I confirm this request uses the exact released Item source and current execution profile.",
                )}
              </span>
            </label>
            <Button
              disabled={
                Boolean(actionBlockReason) ||
                !acknowledged ||
                commandState.kind === "processing"
              }
              type="submit"
              visual="primary"
            >
              {t("Request Item execution")}
            </Button>
          </form>
        </>
      )}
    </section>
  );
}

export function EngineeringBomPublishRequestWorkspace({
  dataSource,
  disabled = false,
  ebom,
  itemPublishDataSource,
  onDirtyChange,
  projectId,
  revision,
}: {
  dataSource?: EngineeringBomPublishRequestDataSource | undefined;
  disabled?: boolean | undefined;
  ebom: EngineeringBomSummaryViewModel;
  itemPublishDataSource?: ItemPublishDataSource | undefined;
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
  const [itemDirty, setItemDirty] = useState(false);
  const [itemInspectorNodeId, setItemInspectorNodeId] = useState<string | null>(
    null,
  );
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
    onDirtyChange?.(dirty || itemDirty);
    return () => {
      onDirtyChange?.(false);
    };
  }, [dirty, itemDirty, onDirtyChange]);

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
          setItemInspectorNodeId(null);
          setItemDirty(false);
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
    setItemInspectorNodeId(null);
    setItemDirty(false);
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
        setItemInspectorNodeId(null);
        setItemDirty(false);
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
                  visual={
                    formOpen ||
                    Boolean(itemInspectorNodeId && itemPublishDataSource)
                      ? "secondary"
                      : "primary"
                  }
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
                    visual={
                      itemInspectorNodeId && itemPublishDataSource
                        ? "secondary"
                        : "primary"
                    }
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
                                setItemInspectorNodeId(null);
                                setItemDirty(false);
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
                                    data-item-inspector-trigger="true"
                                    role="button"
                                    tabIndex={0}
                                    onClick={() => {
                                      setItemInspectorNodeId(node.globalId);
                                      setItemDirty(false);
                                    }}
                                    onKeyDown={(event) => {
                                      if (
                                        event.key === "Enter" ||
                                        event.key === " "
                                      ) {
                                        event.preventDefault();
                                        setItemInspectorNodeId(node.globalId);
                                        setItemDirty(false);
                                      }
                                    }}
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
                    <ItemPublishExecutionInspector
                      active={Boolean(itemInspectorNodeId)}
                      dataSource={itemPublishDataSource}
                      disabled={disabled || commandState.kind === "processing"}
                      onDirtyChange={setItemDirty}
                      projectId={projectId}
                      publishRequest={detail}
                    />
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
