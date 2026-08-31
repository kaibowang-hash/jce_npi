import { useCallback, useEffect, useRef, useState } from "react";

import type {
  ChangeControlDataSource,
  EngineeringChangeCategory,
  EngineeringChangeCommandResult,
  EngineeringChangeContent,
  EngineeringChangeDetail,
  EngineeringChangeImpactAssessment,
  EngineeringChangeList,
  EngineeringChangeRevision,
  EngineeringChangeSummaryReceipt,
} from "../api/change-control-data-source";
import {
  ChangeControlRequestCancelledError,
  engineeringChangeCategories,
} from "../api/change-control-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import { DockedInspector } from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
  SourceSystemIdentity,
} from "../components/primitives";
import type { SemanticTone } from "../domain/view-models";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ResourceState<T> =
  | { kind: "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };

type CommandState =
  | { kind: "idle" }
  | { kind: "processing" }
  | { kind: "succeeded"; receipt: EngineeringChangeSummaryReceipt | null }
  | { kind: "failed"; failure: RequestFailure };

type PreparedCommand =
  | {
      kind: "create";
      content: EngineeringChangeContent;
      idempotencyKey: string;
    }
  | {
      kind: "revise";
      content: EngineeringChangeContent;
      current: EngineeringChangeRevision;
      idempotencyKey: string;
    }
  | {
      kind: "close" | "summary";
      current: EngineeringChangeRevision;
      idempotencyKey: string;
    };

interface EditorState {
  mode: "create" | "revise";
  content: EngineeringChangeContent;
}

function changeStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: EngineeringChangeRevision["state"],
): string {
  switch (state) {
    case "draft":
      return t("Draft");
    case "active":
      return t("Active");
    case "ready_to_close":
      return t("Ready to close");
    case "closed":
      return t("Closed");
    case "cancelled":
      return t("Cancelled");
  }
}

function changeStateTone(
  state: EngineeringChangeRevision["state"],
): SemanticTone {
  if (state === "closed") return "success";
  if (state === "cancelled") return "danger";
  if (state === "ready_to_close") return "warning";
  return state === "active" ? "info" : "neutral";
}

function categoryLabel(
  t: ReturnType<typeof useI18n>["t"],
  category: EngineeringChangeCategory,
): string {
  switch (category) {
    case "product":
      return t("Product");
    case "drawing":
      return t("Drawing");
    case "ebom":
      return t("EBOM");
    case "mbom":
      return t("MBOM");
    case "tooling":
      return t("Tooling");
    case "process":
      return t("Process");
    case "quality":
      return t("Quality");
    case "inventory_wip":
      return t("Inventory and work in progress");
    case "supplier":
      return t("Supplier");
    case "cost":
      return t("Cost");
    case "delivery":
      return t("Delivery");
    case "customer":
      return t("Customer");
  }
}

function impactConclusionLabel(
  t: ReturnType<typeof useI18n>["t"],
  conclusion: EngineeringChangeImpactAssessment["conclusion"],
): string {
  if (conclusion === "affected") return t("Affected");
  if (conclusion === "not_affected") return t("Not affected");
  return t("Pending");
}

function blankContent(actorUserId: string): EngineeringChangeContent {
  return {
    title: "",
    reason: "",
    impactAssessments: engineeringChangeCategories.map((category) => ({
      category,
      conclusion: "pending",
      responsibleUserId: actorUserId,
      rationale: "Pending assessment",
      evidenceReferenceGlobalIds: [],
    })),
    affectedObjects: [],
    implementationTasks: [],
    effectivityRules: [],
    dispositions: [],
    revalidationRequirements: [],
    costSummary: {
      currency: "USD",
      engineeringCost: "0",
      toolingCost: "0",
      scrapCost: "0",
      logisticsCost: "0",
      downtimeMinutes: 0,
      deliveryImpactDays: 0,
    },
    closureEvidence: null,
  };
}

function editableContent(
  revision: EngineeringChangeRevision,
): EngineeringChangeContent {
  return {
    title: revision.title,
    reason: revision.reason,
    impactAssessments: revision.impactAssessments.map((entry) => ({
      ...entry,
      evidenceReferenceGlobalIds: [...entry.evidenceReferenceGlobalIds],
    })),
    affectedObjects: [...revision.affectedObjects],
    implementationTasks: [...revision.implementationTasks],
    effectivityRules: [...revision.effectivityRules],
    dispositions: [...revision.dispositions],
    revalidationRequirements: [...revision.revalidationRequirements],
    costSummary: { ...revision.costSummary },
    closureEvidence: revision.closureEvidence
      ? {
          ...revision.closureEvidence,
          evidenceReferenceGlobalIds: [
            ...revision.closureEvidence.evidenceReferenceGlobalIds,
          ],
        }
      : null,
  };
}

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    failure.problem?.status === 409 ||
    Boolean(failure.problem?.retryable)
  );
}

function LoadingState(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section
      aria-busy="true"
      aria-label={t("Loading engineering changes")}
      className="workspace-resource-state workspace-resource-state--loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">
        {t("Loading engineering changes")}
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
  const status = failure.problem?.status;
  const title =
    status === 401 || status === 403
      ? t("Engineering change access is unavailable")
      : status === 409
        ? t("The engineering change changed before this action completed")
        : failure.kind === "invalid_response" || failure.kind === "unexpected"
          ? t("The engineering change response could not be used safely")
          : t("Engineering changes are unavailable");
  return (
    <section className="workspace-resource-state" role="alert">
      <SemanticStatus label={t("Error")} tone="danger" />
      <h2>{title}</h2>
      <p>
        {status === 409
          ? t("Reload the exact current revision before continuing.")
          : t("No unverified engineering change data was displayed.")}
      </p>
      <RequestFailurePanel failure={failure} />
      {canRetry(failure) ? (
        <Button icon="refresh" onClick={onRetry}>
          {status === 409 ? t("Reload latest data") : t("Retry")}
        </Button>
      ) : null}
    </section>
  );
}

function CommandFeedback({
  onRetry,
  state,
}: {
  onRetry: () => void;
  state: CommandState;
}): React.JSX.Element | null {
  const { t } = useI18n();
  if (state.kind === "idle") return null;
  if (state.kind === "processing") {
    return (
      <p aria-live="polite" role="status">
        <SemanticStatus label={t("Processing")} tone="info" />
      </p>
    );
  }
  if (state.kind === "succeeded") {
    return (
      <div aria-live="polite" className="change-control-feedback" role="status">
        <SemanticStatus label={t("Succeeded")} tone="success" />
        {state.receipt ? (
          <p>
            {t("Implementation summary request state")}:{" "}
            <span data-language-exempt="identifier">{state.receipt.state}</span>
          </p>
        ) : null}
      </div>
    );
  }
  return (
    <div className="change-control-feedback" role="alert">
      <SemanticStatus
        label={canRetry(state.failure) ? t("Retry required") : t("Failed")}
        tone="danger"
      />
      <RequestFailurePanel failure={state.failure} />
      {canRetry(state.failure) ? (
        <Button icon="refresh" onClick={onRetry}>
          {state.failure.problem?.status === 409
            ? t("Reload latest data")
            : t("Retry")}
        </Button>
      ) : null}
    </div>
  );
}

function ChangeEditor({
  editor,
  onCancel,
  onChange,
  onPrepare,
}: {
  editor: EditorState;
  onCancel: () => void;
  onChange: (next: EngineeringChangeContent) => void;
  onPrepare: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const updateImpact = (
    category: EngineeringChangeCategory,
    patch: Partial<EngineeringChangeImpactAssessment>,
  ): void => {
    onChange({
      ...editor.content,
      impactAssessments: editor.content.impactAssessments.map((entry) =>
        entry.category === category ? { ...entry, ...patch } : entry,
      ),
    });
  };
  return (
    <Panel
      className="change-control-editor"
      title={
        editor.mode === "create"
          ? t("New engineering change")
          : t("Revise engineering change")
      }
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onPrepare();
        }}
      >
        <div className="change-control-editor__header">
          <label className="field-control">
            <span>{t("Title")}</span>
            <TextInput
              maxLength={280}
              onChange={(event) => {
                onChange({
                  ...editor.content,
                  title: event.currentTarget.value,
                });
              }}
              required
              value={editor.content.title}
            />
          </label>
          <label className="field-control change-control-editor__reason">
            <span>{t("Change reason")}</span>
            <textarea
              maxLength={4000}
              onChange={(event) => {
                onChange({
                  ...editor.content,
                  reason: event.currentTarget.value,
                });
              }}
              required
              rows={3}
              value={editor.content.reason}
            />
          </label>
        </div>
        <div className="change-control-impact-grid">
          {editor.content.impactAssessments.map((entry) => (
            <fieldset key={entry.category}>
              <legend>{categoryLabel(t, entry.category)}</legend>
              <label className="field-control">
                <span>{t("Conclusion")}</span>
                <Select
                  onChange={(event) => {
                    updateImpact(entry.category, {
                      conclusion: event.currentTarget
                        .value as EngineeringChangeImpactAssessment["conclusion"],
                    });
                  }}
                  value={entry.conclusion}
                >
                  <option value="pending">{t("Pending")}</option>
                  <option value="not_affected">{t("Not affected")}</option>
                  <option value="affected">{t("Affected")}</option>
                </Select>
              </label>
              <label className="field-control">
                <span>{t("Responsible user")}</span>
                <TextInput
                  maxLength={254}
                  onChange={(event) => {
                    updateImpact(entry.category, {
                      responsibleUserId: event.currentTarget.value,
                    });
                  }}
                  required
                  type="email"
                  value={entry.responsibleUserId}
                />
              </label>
              <label className="field-control">
                <span>{t("Rationale")}</span>
                <textarea
                  maxLength={4000}
                  onChange={(event) => {
                    updateImpact(entry.category, {
                      rationale: event.currentTarget.value,
                    });
                  }}
                  required
                  rows={2}
                  value={entry.rationale}
                />
              </label>
            </fieldset>
          ))}
        </div>
        <div className="change-control-editor__actions">
          <Button onClick={onCancel}>{t("Cancel")}</Button>
          <Button type="submit" visual="primary">
            {editor.mode === "create"
              ? t("Review engineering change")
              : t("Review engineering change revision")}
          </Button>
        </div>
      </form>
    </Panel>
  );
}

function ChangeInspector({
  detail,
}: {
  detail: EngineeringChangeDetail;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const revision = detail.currentRevision;
  return (
    <DockedInspector title={t("Engineering change inspector")}>
      <DefinitionList
        rows={[
          {
            label: t("Change ID"),
            value: revision.changeGlobalId,
            exempt: "identifier",
          },
          {
            label: t("Revision"),
            value: formatNumber(locale, revision.revision, 0),
            exempt: "identifier",
          },
          {
            label: t("Snapshot hash"),
            value: revision.snapshotHash,
            exempt: "identifier",
          },
          {
            label: t("Created by"),
            value: revision.createdByUserId,
            exempt: "identifier",
          },
          {
            label: t("Created at"),
            value: formatDateTime(locale, revision.createdAt),
          },
          {
            label: t("Events"),
            value: formatNumber(locale, detail.events.length, 0),
          },
        ]}
      />
      <h3>{t("ERP formal observation")}</h3>
      {revision.formalChange ? (
        <>
          <SourceSystemIdentity emphasized sourceSystem="ERPNEXT" />
          <DefinitionList
            rows={[
              {
                label: t("Document type"),
                value: revision.formalChange.doctype,
                exempt: "identifier",
              },
              {
                label: t("Document name"),
                value: revision.formalChange.documentName,
                exempt: "business-data",
              },
              {
                label: t("Raw ERP status"),
                value: revision.formalChange.rawStatus,
                exempt: "business-data",
              },
              {
                label: t("Source version"),
                value: revision.formalChange.sourceVersion,
                exempt: "identifier",
              },
              {
                label: t("Observed at"),
                value: formatDateTime(locale, revision.formalChange.observedAt),
              },
            ]}
          />
        </>
      ) : (
        <p>{t("No formal ERP engineering change has been observed.")}</p>
      )}
    </DockedInspector>
  );
}

function DetailWorkspace({
  detail,
  onClose,
  onRevise,
  onSummary,
}: {
  detail: EngineeringChangeDetail;
  onClose: () => void;
  onRevise: () => void;
  onSummary: () => void;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const revision = detail.currentRevision;
  const affectedCount = revision.impactAssessments.filter(
    (entry) => entry.conclusion === "affected",
  ).length;
  const pendingCount = revision.impactAssessments.filter(
    (entry) => entry.conclusion === "pending",
  ).length;
  return (
    <div className="change-control-detail-layout">
      <div className="change-control-detail">
        <Panel
          actions={
            <>
              {detail.permissions.canRevise && revision.state !== "closed" ? (
                <Button icon="document" onClick={onRevise}>
                  {t("Revise")}
                </Button>
              ) : null}
              <Button
                disabled={!sessionCommandContext}
                icon="play"
                onClick={onSummary}
              >
                {t("Request implementation summary")}
              </Button>
              {detail.permissions.canClose && revision.readyToClose ? (
                <Button
                  disabled={!sessionCommandContext}
                  onClick={onClose}
                  visual="primary"
                >
                  {t("Close engineering change")}
                </Button>
              ) : null}
            </>
          }
          title={t("Engineering change detail")}
        >
          <h3 data-language-exempt="business-data">{revision.title}</h3>
          <div className="change-control-summary-strip">
            <SemanticStatus
              label={changeStateLabel(t, revision.state)}
              tone={changeStateTone(revision.state)}
            />
            <span>
              {t("Revision {{revision}}", {
                revision: formatNumber(locale, revision.revision, 0),
              })}
            </span>
            <span>
              {t("{{count}} affected areas", {
                count: formatNumber(locale, affectedCount, 0),
              })}
            </span>
            <span>
              {t("{{count}} pending assessments", {
                count: formatNumber(locale, pendingCount, 0),
              })}
            </span>
          </div>
          <p data-language-exempt="business-data">{revision.reason}</p>
          {!sessionCommandContext ? (
            <p className="scenario-banner scenario-banner--read_only">
              {t("Session verification is required before any command.")}
            </p>
          ) : null}
        </Panel>
        <Panel title={t("Impact assessment matrix")}>
          <div className="engineering-table-scroll" tabIndex={0}>
            <table className="engineering-table">
              <thead>
                <tr>
                  <th>{t("Area")}</th>
                  <th>{t("Conclusion")}</th>
                  <th>{t("Responsible user")}</th>
                  <th>{t("Rationale")}</th>
                  <th>{t("Evidence")}</th>
                </tr>
              </thead>
              <tbody>
                {revision.impactAssessments.map((entry) => (
                  <tr key={entry.category}>
                    <th scope="row">{categoryLabel(t, entry.category)}</th>
                    <td>
                      <SemanticStatus
                        label={impactConclusionLabel(t, entry.conclusion)}
                        tone={
                          entry.conclusion === "affected"
                            ? "warning"
                            : entry.conclusion === "not_affected"
                              ? "success"
                              : "neutral"
                        }
                      />
                    </td>
                    <td data-language-exempt="identifier">
                      {entry.responsibleUserId}
                    </td>
                    <td data-language-exempt="business-data">
                      {entry.rationale}
                    </td>
                    <td>
                      {formatNumber(
                        locale,
                        entry.evidenceReferenceGlobalIds.length,
                        0,
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <div className="change-control-evidence-grid">
          <Panel title={t("Affected controlled objects")}>
            <DefinitionList
              rows={[
                {
                  label: t("Objects"),
                  value: formatNumber(
                    locale,
                    revision.affectedObjects.length,
                    0,
                  ),
                },
                {
                  label: t("Implementation tasks"),
                  value: formatNumber(
                    locale,
                    revision.implementationTasks.length,
                    0,
                  ),
                },
                {
                  label: t("Effectivity rules"),
                  value: formatNumber(
                    locale,
                    revision.effectivityRules.length,
                    0,
                  ),
                },
              ]}
            />
          </Panel>
          <Panel title={t("Disposition and revalidation")}>
            <DefinitionList
              rows={[
                {
                  label: t("Dispositions"),
                  value: formatNumber(locale, revision.dispositions.length, 0),
                },
                {
                  label: t("Revalidation requirements"),
                  value: formatNumber(
                    locale,
                    revision.revalidationRequirements.length,
                    0,
                  ),
                },
                {
                  label: t("Ready to close"),
                  value: revision.readyToClose ? t("Yes") : t("No"),
                },
              ]}
            />
          </Panel>
        </div>
      </div>
      <ChangeInspector detail={detail} />
    </div>
  );
}

export interface ProjectChangeWorkspaceProps {
  readonly dataSource: ChangeControlDataSource;
  readonly projectId: string;
  readonly reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}

export function ProjectChangeWorkspace({
  dataSource,
  projectId,
  reportWorkspaceDirty,
}: ProjectChangeWorkspaceProps): React.JSX.Element {
  const { sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [list, setList] = useState<ResourceState<EngineeringChangeList>>({
    kind: "loading",
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] =
    useState<ResourceState<EngineeringChangeDetail> | null>(null);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [review, setReview] = useState<PreparedCommand | null>(null);
  const [commandState, setCommandState] = useState<CommandState>({
    kind: "idle",
  });
  const commandController = useRef<AbortController | null>(null);
  const retryCommand = useRef<PreparedCommand | null>(null);

  const loadList = useCallback((): void => {
    setList({ kind: "loading" });
    setDetail(null);
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void dataSource
      .loadChanges(projectId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setList({ kind: "loaded", value });
        setSelectedId((current) =>
          current &&
          value.items.some((item) => item.change.globalId === current)
            ? current
            : (value.items[0]?.change.globalId ?? null),
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ChangeControlRequestCancelledError
        )
          return;
        setList({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, projectId]);

  useEffect(() => {
    if (!selectedId) return undefined;
    const controller = new AbortController();
    const cancelled = (): boolean => controller.signal.aborted;
    const load = async (): Promise<void> => {
      await Promise.resolve();
      if (cancelled()) return;
      setDetail({ kind: "loading" });
      try {
        const value = await dataSource.loadChange(
          projectId,
          selectedId,
          controller.signal,
        );
        if (!cancelled()) setDetail({ kind: "loaded", value });
      } catch (error: unknown) {
        if (cancelled() || error instanceof ChangeControlRequestCancelledError)
          return;
        setDetail({ kind: "failed", failure: toRequestFailure(error) });
      }
    };
    void load();
    return () => {
      controller.abort();
    };
  }, [dataSource, projectId, selectedId, attempt]);

  useEffect(
    () => () => {
      commandController.current?.abort();
    },
    [],
  );

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!editor) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: `${projectId}:engineering-change`,
      returnFocusTarget: () =>
        document.getElementById("project-workspace-tab-change-control"),
      version: "unsaved-engineering-change-revision",
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [editor, projectId, reportWorkspaceDirty]);

  const execute = useCallback(
    (operation: PreparedCommand): void => {
      if (!sessionCommandContext) return;
      commandController.current?.abort();
      const controller = new AbortController();
      commandController.current = controller;
      setCommandState({ kind: "processing" });
      const context = {
        csrfToken: sessionCommandContext.csrfToken,
        idempotencyKey: operation.idempotencyKey,
        signal: controller.signal,
      };
      let request: Promise<
        EngineeringChangeCommandResult | EngineeringChangeSummaryReceipt
      >;
      if (operation.kind === "create") {
        request = dataSource.createChange(
          projectId,
          operation.content,
          context,
        );
      } else if (operation.kind === "revise") {
        request = dataSource.reviseChange(
          projectId,
          operation.current,
          operation.content,
          context,
        );
      } else if (operation.kind === "close") {
        request = dataSource.closeChange(projectId, operation.current, context);
      } else {
        request = dataSource.requestImplementationSummary(
          projectId,
          operation.current,
          context,
        );
      }
      void request
        .then((result) => {
          if (controller.signal.aborted) return;
          retryCommand.current = null;
          setEditor(null);
          setReview(null);
          setCommandState({
            kind: "succeeded",
            receipt: "requestGlobalId" in result ? result : null,
          });
          if ("change" in result) setSelectedId(result.change.globalId);
          setAttempt((value) => value + 1);
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            error instanceof ChangeControlRequestCancelledError
          )
            return;
          setReview(null);
          setCommandState({ kind: "failed", failure: toRequestFailure(error) });
        });
    },
    [dataSource, projectId, sessionCommandContext],
  );

  const prepareEditor = (): void => {
    if (!editor || !sessionCommandContext) return;
    const operation: PreparedCommand | null =
      editor.mode === "create"
        ? {
            kind: "create",
            content: editor.content,
            idempotencyKey: `engineering-change-create-${globalThis.crypto.randomUUID()}`,
          }
        : detail?.kind === "loaded"
          ? {
              kind: "revise",
              content: editor.content,
              current: detail.value.currentRevision,
              idempotencyKey: `engineering-change-revise-${globalThis.crypto.randomUUID()}`,
            }
          : null;
    if (!operation) return;
    retryCommand.current = operation;
    setReview(operation);
  };

  const prepareCurrent = (kind: "close" | "summary"): void => {
    if (detail?.kind !== "loaded" || !sessionCommandContext) return;
    const operation: PreparedCommand = {
      kind,
      current: detail.value.currentRevision,
      idempotencyKey: `engineering-change-${kind}-${globalThis.crypto.randomUUID()}`,
    };
    retryCommand.current = operation;
    setReview(operation);
  };

  if (list.kind === "loading") return <LoadingState />;
  if (list.kind === "failed") {
    return <FailureState failure={list.failure} onRetry={loadList} />;
  }
  if (!list.value.permissions.canView) {
    return (
      <section className="workspace-resource-state" role="status">
        <SemanticStatus label={t("No permission")} tone="warning" />
        <h2>{t("Engineering change access is unavailable")}</h2>
        <p>{t("Project membership and backend permission are required.")}</p>
      </section>
    );
  }

  const selectedListItem = list.value.items.find(
    (item) => item.change.globalId === selectedId,
  );
  const drifted =
    selectedListItem &&
    detail?.kind === "loaded" &&
    selectedListItem.currentRevision.snapshotHash !==
      detail.value.currentRevision.snapshotHash;

  return (
    <section className="change-control-workspace">
      <Panel
        actions={
          list.value.permissions.canCreate ? (
            <Button
              icon="add"
              onClick={() => {
                setCommandState({ kind: "idle" });
                setEditor({
                  mode: "create",
                  content: blankContent(sessionCommandContext?.userId ?? ""),
                });
              }}
              visual="primary"
            >
              {t("New engineering change")}
            </Button>
          ) : undefined
        }
        title={t("Change control")}
      >
        <p>
          {t(
            "Control NPI-owned impact, version, effectivity and closure evidence while ERP formal change truth remains read only.",
          )}
        </p>
        {!list.value.permissions.canCreate ? (
          <SemanticStatus label={t("Read only")} tone="info" />
        ) : null}
        {list.value.items.length === 0 ? (
          <div className="workspace-resource-state" role="status">
            <SemanticStatus label={t("Empty")} tone="neutral" />
            <p>
              {t("No engineering changes have been recorded for this Project.")}
            </p>
          </div>
        ) : (
          <div
            aria-label={t("Engineering changes")}
            className="change-control-list"
          >
            {list.value.items.map((item) => (
              <button
                aria-current={
                  item.change.globalId === selectedId ? "true" : undefined
                }
                className="change-control-list__item"
                key={item.change.globalId}
                onClick={() => {
                  if (editor) return;
                  setDetail({ kind: "loading" });
                  setSelectedId(item.change.globalId);
                  setCommandState({ kind: "idle" });
                }}
                type="button"
              >
                <span data-language-exempt="business-data">
                  {item.change.title}
                </span>
                <SemanticStatus
                  label={changeStateLabel(t, item.change.state)}
                  tone={changeStateTone(item.change.state)}
                />
                <span data-language-exempt="identifier">
                  {t("Revision {{revision}}", {
                    revision: item.change.currentRevisionNumber,
                  })}
                </span>
              </button>
            ))}
          </div>
        )}
      </Panel>

      {drifted ? (
        <div className="scenario-banner scenario-banner--conflict" role="alert">
          <SemanticStatus label={t("Drifted")} tone="warning" />
          <span>
            {t("Reload the exact current revision before continuing.")}
          </span>
          <Button icon="refresh" onClick={loadList}>
            {t("Reload latest data")}
          </Button>
        </div>
      ) : null}

      {editor ? (
        <ChangeEditor
          editor={editor}
          onCancel={() => {
            setEditor(null);
            setCommandState({ kind: "idle" });
          }}
          onChange={(content) => {
            setEditor({ ...editor, content });
          }}
          onPrepare={prepareEditor}
        />
      ) : selectedId && detail?.kind === "loading" ? (
        <LoadingState />
      ) : selectedId && detail?.kind === "failed" ? (
        <FailureState failure={detail.failure} onRetry={loadList} />
      ) : detail?.kind === "loaded" ? (
        <DetailWorkspace
          detail={detail.value}
          onClose={() => {
            prepareCurrent("close");
          }}
          onRevise={() => {
            setCommandState({ kind: "idle" });
            setEditor({
              mode: "revise",
              content: editableContent(detail.value.currentRevision),
            });
          }}
          onSummary={() => {
            prepareCurrent("summary");
          }}
        />
      ) : null}

      <CommandFeedback
        onRetry={() => {
          if (
            commandState.kind === "failed" &&
            commandState.failure.problem?.status === 409
          ) {
            retryCommand.current = null;
            setCommandState({ kind: "idle" });
            loadList();
            return;
          }
          const operation = retryCommand.current;
          if (operation) execute(operation);
        }}
        state={commandState}
      />

      {review ? (
        <ImpactReview
          confirmLabel={
            review.kind === "create"
              ? t("Create engineering change")
              : review.kind === "revise"
                ? t("Append engineering change revision")
                : review.kind === "close"
                  ? t("Close engineering change")
                  : t("Request implementation summary")
          }
          contextRows={[
            {
              exempt: "identifier",
              label: t("Project ID"),
              value: projectId,
            },
          ]}
          details={{
            audit: t(
              "The command, actor, receipt and exact version are audited.",
            ),
            failureHandling: t(
              "A failed transaction retains no partial revision. Retry uses the same command identity.",
            ),
            impact:
              review.kind === "create"
                ? t("Creates the first immutable engineering change revision.")
                : review.kind === "revise"
                  ? t("Appends one immutable successor revision.")
                  : review.kind === "close"
                    ? t("Closes the exact ready engineering change revision.")
                    : t(
                        "Queues an exact implementation summary for ERP delivery.",
                      ),
            irreversible:
              review.kind === "summary"
                ? t(
                    "The queued operation remains visible for retry and reconciliation.",
                  )
                : t(
                    "Immutable revisions and closure facts cannot be overwritten.",
                  ),
            objectIdentity:
              review.kind === "create"
                ? projectId
                : review.current.changeGlobalId,
            permission: t(
              "Backend Project membership and operation permission are required.",
            ),
            version:
              review.kind === "create"
                ? t("New revision")
                : t("Revision {{revision}}", {
                    revision: review.current.revision,
                  }),
          }}
          onCancel={() => {
            setReview(null);
          }}
          onConfirm={() => {
            execute(review);
          }}
          reasonRequired={false}
          title={t("Review engineering change command")}
        />
      ) : null}
    </section>
  );
}
