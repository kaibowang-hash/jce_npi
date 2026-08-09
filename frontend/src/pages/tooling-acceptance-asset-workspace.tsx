import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  TOOL_ASSET_MOCK_ACKNOWLEDGEMENT,
  toolingAcceptanceCategories,
  type CreateToolAssetRequestCommand,
  type CreateToolingAcceptanceEvidenceRevisionCommand,
  type ToolingAcceptanceAssetContextViewModel,
  type ToolingAcceptanceCategory,
  type ToolingAcceptanceChecklistItemInputViewModel,
  type ToolingAcceptanceEvidenceRevisionViewModel,
  type ToolingCommandContext,
  type ToolingDataSource,
  type ToolingEvidenceDisposition,
  type ToolingMasterSummaryViewModel,
  type ToolingRevisionCollectionViewModel,
  type ToolingSetCollectionViewModel,
} from "../api/tooling-data-source";
import { ToolingRequestCancelledError } from "../api/tooling-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ResourceState =
  | { kind: "loading" }
  | { kind: "loaded"; value: WorkspaceResources }
  | { kind: "failed"; failure: RequestFailure };
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

interface WorkspaceResources {
  acceptance: ToolingAcceptanceAssetContextViewModel;
  requests: Awaited<ReturnType<ToolingDataSource["loadToolAssetRequests"]>>;
  revisions: ToolingRevisionCollectionViewModel;
  sets: ToolingSetCollectionViewModel;
}

interface ChecklistDraft {
  category: ToolingAcceptanceCategory;
  disposition: ToolingEvidenceDisposition;
  evidence: ToolingAcceptanceChecklistItemInputViewModel["evidence"];
  fileRevisionGlobalId: string;
  fileOptimisticVersion: string;
  frappeContentHash: string;
  note: string;
  requirementKey: string;
  requirementStatement: string;
  sha256: string;
}

interface AcceptanceDraft {
  acceptanceGlobalId: string;
  expectedVersion: string;
  reason: string;
  setId: string;
  checklist: ChecklistDraft[];
}

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function categorySource(category: ToolingAcceptanceCategory): string {
  switch (category) {
    case "technical":
      return "Technical requirements";
    case "quality":
      return "Quality requirements";
    case "cycle_capacity":
      return "Cycle and capacity requirements";
    case "spares_maintenance":
      return "Spares and maintenance requirements";
    case "documents":
      return "Controlled document requirements";
    case "warranty_responsibility":
      return "Warranty and responsibility requirements";
    case "cost":
      return "Cost requirements";
    case "safety_interface":
      return "Safety and interface requirements";
    case "asset_location":
      return "Asset and location requirements";
  }
}

function categoryLabel(
  t: ReturnType<typeof useI18n>["t"],
  category: ToolingAcceptanceCategory,
): string {
  switch (category) {
    case "technical":
      return t("Technical requirements");
    case "quality":
      return t("Quality requirements");
    case "cycle_capacity":
      return t("Cycle and capacity requirements");
    case "spares_maintenance":
      return t("Spares and maintenance requirements");
    case "documents":
      return t("Controlled document requirements");
    case "warranty_responsibility":
      return t("Warranty and responsibility requirements");
    case "cost":
      return t("Cost requirements");
    case "safety_interface":
      return t("Safety and interface requirements");
    case "asset_location":
      return t("Asset and location requirements");
  }
}

function dispositionLabel(
  t: ReturnType<typeof useI18n>["t"],
  disposition: ToolingEvidenceDisposition,
): string {
  switch (disposition) {
    case "evidence_recorded":
      return t("Evidence recorded");
    case "evidence_missing":
      return t("Evidence missing");
    case "not_applicable_asserted":
      return t("Not applicable with reason");
  }
}

function checklistDraft(
  predecessor: ToolingAcceptanceEvidenceRevisionViewModel | null,
): ChecklistDraft[] {
  return toolingAcceptanceCategories.map((category) => {
    const previous = predecessor?.checklist.find(
      (item) => item.category === category,
    );
    const evidence = previous?.evidence[0];
    return {
      category,
      disposition: previous?.disposition ?? "evidence_missing",
      evidence:
        previous?.evidence.map((item) => ({
          fileOptimisticVersion: item.fileOptimisticVersion,
          fileRevisionGlobalId: item.fileRevisionGlobalId,
          frappeContentHash: item.frappeContentHash,
          role: item.role,
          sha256: item.sha256,
        })) ?? [],
      fileOptimisticVersion: evidence
        ? String(evidence.fileOptimisticVersion)
        : "1",
      fileRevisionGlobalId: evidence?.fileRevisionGlobalId ?? "",
      frappeContentHash: evidence?.frappeContentHash ?? "",
      note: previous?.note ?? "",
      requirementKey: previous?.requirementKey ?? `acceptance.${category}`,
      requirementStatement:
        previous?.requirementStatement ?? categorySource(category),
      sha256: evidence?.sha256 ?? "",
    };
  });
}

function latestByAcceptance(
  values: readonly ToolingAcceptanceEvidenceRevisionViewModel[],
): readonly ToolingAcceptanceEvidenceRevisionViewModel[] {
  const latest = new Map<string, ToolingAcceptanceEvidenceRevisionViewModel>();
  for (const value of values) {
    const current = latest.get(value.acceptanceGlobalId);
    if (!current || current.acceptanceVersion < value.acceptanceVersion)
      latest.set(value.acceptanceGlobalId, value);
  }
  return [...latest.values()].sort((left, right) =>
    left.acceptanceGlobalId.localeCompare(right.acceptanceGlobalId),
  );
}

function newAcceptanceDraft(
  setId: string,
  predecessor: ToolingAcceptanceEvidenceRevisionViewModel | null,
): AcceptanceDraft {
  return {
    acceptanceGlobalId: predecessor?.acceptanceGlobalId ?? "",
    checklist: checklistDraft(predecessor),
    expectedVersion: predecessor ? String(predecessor.acceptanceVersion) : "",
    reason: "",
    setId,
  };
}

export default function ToolingAcceptanceAssetWorkspace({
  dataSource,
  master,
  projectId,
  reportWorkspaceDirty,
}: {
  dataSource: ToolingDataSource;
  master: ToolingMasterSummaryViewModel;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [draft, setDraft] = useState<AcceptanceDraft | null>(null);
  const [selectedAcceptanceId, setSelectedAcceptanceId] = useState<string>("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const retryCommand = useRef<(() => void) | null>(null);
  const editorTrigger = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      dataSource.loadAcceptanceAssets(
        projectId,
        master.globalId,
        controller.signal,
      ),
      dataSource.loadToolAssetRequests(
        projectId,
        master.globalId,
        controller.signal,
      ),
      dataSource.loadSets(projectId, master.globalId, controller.signal),
      dataSource.loadToolingRevisions(
        projectId,
        master.globalId,
        controller.signal,
      ),
    ])
      .then(([acceptance, requests, sets, revisions]) => {
        if (controller.signal.aborted) return;
        setResource({
          kind: "loaded",
          value: { acceptance, requests, revisions, sets },
        });
        setSelectedAcceptanceId((current) =>
          current !== ""
            ? current
            : (latestByAcceptance(acceptance.acceptanceRevisions).at(-1)
                ?.globalId ?? ""),
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ToolingRequestCancelledError
        )
          return;
        setResource({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, master.globalId, projectId]);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!draft) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: `${master.globalId}:acceptance-assets`,
      returnFocusTarget: () => editorTrigger.current,
      version: "unsaved-tooling-acceptance-evidence",
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [draft, master.globalId, reportWorkspaceDirty]);

  const loaded = resource.kind === "loaded" ? resource.value : null;
  const latestAcceptances = useMemo(
    () => latestByAcceptance(loaded?.acceptance.acceptanceRevisions ?? []),
    [loaded?.acceptance.acceptanceRevisions],
  );
  const selectedAcceptance =
    latestAcceptances.find((item) => item.globalId === selectedAcceptanceId) ??
    latestAcceptances.at(-1) ??
    null;
  const selectedSet = loaded?.sets.items.find(
    (item) => item.globalId === selectedAcceptance?.toolingSetGlobalId,
  );
  const processing = command.kind === "processing";
  const canRecord = Boolean(
    loaded?.acceptance.permissions.recordEvidence && sessionCommandContext,
  );
  const canPrepareMock = Boolean(
    loaded?.acceptance.permissions.prepareMockAssetRequest &&
    sessionCommandContext &&
    selectedAcceptance,
  );

  const reload = useCallback(() => {
    setResource({ kind: "loading" });
    setAttempt((current) => current + 1);
  }, []);

  const runCommand = useCallback(
    <T,>(
      label: string,
      prefix: string,
      operation: (context: ToolingCommandContext) => Promise<T>,
      after: (value: T) => void = () => undefined,
    ): void => {
      if (!sessionCommandContext) return;
      const idempotencyKey = `${prefix}-${globalThis.crypto.randomUUID()}`;
      const execute = (): void => {
        const controller = new AbortController();
        setCommand({ kind: "processing", label });
        void operation({
          ...sessionCommandContext,
          idempotencyKey,
          signal: controller.signal,
        })
          .then((value) => {
            after(value);
            setDraft(null);
            setFormError(null);
            setAcknowledged(false);
            setCommand({ kind: "idle" });
            reload();
          })
          .catch((error: unknown) => {
            if (
              !controller.signal.aborted &&
              !(error instanceof ToolingRequestCancelledError)
            )
              setCommand({ kind: "failed", failure: toRequestFailure(error) });
          });
      };
      retryCommand.current = execute;
      execute();
    },
    [reload, sessionCommandContext],
  );

  const openAcceptance = (
    trigger: HTMLElement,
    setId: string,
    predecessor: ToolingAcceptanceEvidenceRevisionViewModel | null,
  ): void => {
    editorTrigger.current = trigger;
    setDraft(newAcceptanceDraft(setId, predecessor));
    setFormError(null);
  };

  const submitAcceptance = (): void => {
    if (!loaded || !draft || !sessionCommandContext) return;
    const toolingSet = loaded.sets.items.find(
      (item) => item.globalId === draft.setId,
    );
    if (!toolingSet || "state" in toolingSet.sourceRevision) {
      setFormError(
        t(
          "Select a physical Tooling Set with an exact Tooling Revision binding.",
        ),
      );
      return;
    }
    const binding = toolingSet.sourceRevision;
    const revision = loaded.revisions.items.find(
      (item) => item.globalId === binding.toolingRevisionGlobalId,
    );
    const invalidItem = draft.checklist.some((item) => {
      if (item.disposition === "evidence_recorded") {
        return (
          !item.fileRevisionGlobalId.trim() ||
          !Number.isInteger(Number(item.fileOptimisticVersion)) ||
          Number(item.fileOptimisticVersion) < 1 ||
          !item.frappeContentHash.trim() ||
          !item.sha256.trim()
        );
      }
      if (item.disposition === "not_applicable_asserted")
        return !item.note.trim();
      return false;
    });
    if (!revision || !draft.reason.trim() || invalidItem) {
      setFormError(
        t("Complete the exact acceptance evidence fields and append reason."),
      );
      return;
    }
    const checklist: ToolingAcceptanceChecklistItemInputViewModel[] =
      draft.checklist.map((item) => ({
        category: item.category,
        disposition: item.disposition,
        evidence:
          item.disposition === "evidence_recorded"
            ? [
                {
                  fileOptimisticVersion: Number(item.fileOptimisticVersion),
                  fileRevisionGlobalId: item.fileRevisionGlobalId.trim(),
                  frappeContentHash: item.frappeContentHash.trim(),
                  role: "checklist",
                  sha256: item.sha256.trim(),
                },
                ...item.evidence.slice(1),
              ]
            : [],
        note: item.note.trim() || null,
        requirementKey: item.requirementKey,
        requirementStatement: item.requirementStatement,
        responsibleMember: null,
      }));
    const commandValue: CreateToolingAcceptanceEvidenceRevisionCommand = {
      ...(draft.acceptanceGlobalId
        ? {
            acceptanceGlobalId: draft.acceptanceGlobalId,
            expectedVersion: Number(draft.expectedVersion),
          }
        : {}),
      assetActions: [],
      checklist,
      reason: draft.reason.trim(),
      repairs: [],
      setRevisionBindingGlobalId: binding.globalId,
      setRevisionBindingSnapshotHash: binding.snapshotHash,
      spareRecommendations: [],
      toolingRevisionGlobalId: revision.globalId,
      toolingRevisionNumber: revision.revisionNumber,
      toolingRevisionSnapshotHash: revision.snapshotHash,
      toolingSetGlobalId: toolingSet.globalId,
      toolingSetSnapshotHash: toolingSet.snapshotHash,
    };
    runCommand(
      t("Appending immutable acceptance evidence Revision"),
      "tooling-acceptance",
      (context) =>
        dataSource.createToolingAcceptanceRevision(
          projectId,
          master.globalId,
          commandValue,
          context,
        ),
      (created) => {
        setSelectedAcceptanceId(created.globalId);
      },
    );
  };

  const submitMockRequest = (): void => {
    if (
      !loaded ||
      !selectedAcceptance ||
      !selectedSet ||
      !sessionCommandContext ||
      !acknowledged
    ) {
      setFormError(
        t(
          "Confirm the Mock-only acknowledgement before preparing the request.",
        ),
      );
      return;
    }
    if ("state" in selectedSet.sourceRevision) {
      setFormError(
        t(
          "The selected acceptance evidence no longer has an exact Set binding.",
        ),
      );
      return;
    }
    const commandValue: CreateToolAssetRequestCommand = {
      acceptanceRevisionGlobalId: selectedAcceptance.globalId,
      acceptanceSnapshotHash: selectedAcceptance.snapshotHash,
      acceptanceVersion: selectedAcceptance.acceptanceVersion,
      acknowledgement: TOOL_ASSET_MOCK_ACKNOWLEDGEMENT,
      expectedBindingSnapshotHash:
        selectedAcceptance.setRevisionBindingSnapshotHash,
      expectedToolingMasterSnapshotHash: master.snapshotHash,
      expectedToolingRevisionNumber: selectedAcceptance.toolingRevisionNumber,
      expectedToolingRevisionSnapshotHash:
        selectedAcceptance.toolingRevisionSnapshotHash,
      expectedToolingSetSnapshotHash: selectedAcceptance.toolingSetSnapshotHash,
      targetMode: "mock",
    };
    runCommand(
      t("Preparing local Mock Asset request"),
      "tooling-asset-mock",
      (context) =>
        dataSource.createToolAssetRequest(
          projectId,
          master.globalId,
          selectedSet.globalId,
          commandValue,
          context,
        ),
    );
  };

  if (resource.kind === "loading") {
    return (
      <section
        aria-busy="true"
        aria-label={t("Loading acceptance and Asset workspace")}
        className="workspace-resource-state workspace-resource-state--loading"
        id="tooling-acceptance-asset-workspace"
        role="status"
      >
        <div className="skeleton skeleton--title" />
        <div className="skeleton" />
        <span className="visually-hidden">
          {t("Loading acceptance and Asset workspace")}
        </span>
      </section>
    );
  }

  if (resource.kind === "failed") {
    return (
      <section id="tooling-acceptance-asset-workspace">
        <RequestFailurePanel failure={resource.failure} />
        <Button onClick={reload}>
          {t("Retry acceptance and Asset workspace")}
        </Button>
      </section>
    );
  }

  const value = resource.value;
  const boundSets = value.sets.items.filter(
    (item) => !("state" in item.sourceRevision),
  );

  return (
    <section
      aria-label={t("Acceptance evidence and Asset preparation")}
      className="tooling-acceptance"
      id="tooling-acceptance-asset-workspace"
    >
      <header className="tooling-acceptance__header">
        <div>
          <span className="eyebrow">{t("Tooling assurance")}</span>
          <h2>{t("Acceptance evidence and Asset preparation")}</h2>
          <p>
            {t(
              "Record immutable evidence by physical Set, then validate a local Mock request without inferring approval or ERPNext execution.",
            )}
          </p>
        </div>
        <div className="tooling-acceptance__status-strip">
          <SemanticStatus label={t("Approval unavailable")} tone="warning" />
          <SemanticStatus label={t("Mock validation only")} tone="info" />
          <SemanticStatus label={t("Dispatch prohibited")} tone="neutral" />
        </div>
      </header>

      {!sessionCommandContext &&
      (value.acceptance.permissions.recordEvidence ||
        value.acceptance.permissions.prepareMockAssetRequest) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>
            {t("Acceptance and Asset commands are read only in this session.")}
          </span>
          <span>
            {t(
              "Session verification is required before a command can be submitted.",
            )}
          </span>
        </div>
      ) : null}
      {!value.acceptance.permissions.recordEvidence &&
      !value.acceptance.permissions.prepareMockAssetRequest ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>
            {t("Acceptance and Asset evidence is read only for this user.")}
          </span>
          <span>
            {t("The server controls evidence and Mock-request permissions.")}
          </span>
        </div>
      ) : null}
      {command.kind === "processing" ? (
        <div
          aria-busy="true"
          className="scenario-banner scenario-banner--processing"
          role="status"
        >
          <span>{command.label}</span>
          <span>
            {t("The command is processing. Keep this workspace open.")}
          </span>
        </div>
      ) : null}
      {command.kind === "failed" ? (
        <div className="tooling-command-failure">
          <RequestFailurePanel failure={command.failure} />
          {canRetry(command.failure) ? (
            <Button
              disabled={processing}
              onClick={() => retryCommand.current?.()}
            >
              {t("Retry exact command")}
            </Button>
          ) : null}
        </div>
      ) : null}

      <div className="tooling-acceptance__truth-grid">
        <Panel title={t("Acceptance evidence lineage")}>
          {latestAcceptances.length ? (
            <div
              aria-label={t("Acceptance evidence lineage")}
              className="table-scroll"
              tabIndex={0}
            >
              <table className="data-table tooling-acceptance__lineage-table">
                <thead>
                  <tr>
                    <th>{t("Physical Set")}</th>
                    <th>{t("Evidence Revision")}</th>
                    <th>{t("Recorded")}</th>
                    <th>{t("Missing")}</th>
                    <th>{t("Not applicable")}</th>
                    <th>{t("Actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {latestAcceptances.map((item) => {
                    const set = value.sets.items.find(
                      (candidate) =>
                        candidate.globalId === item.toolingSetGlobalId,
                    );
                    const recorded = item.categoryCoverage.reduce(
                      (total, category) => total + category.recordedCount,
                      0,
                    );
                    const missing = item.categoryCoverage.reduce(
                      (total, category) => total + category.missingCount,
                      0,
                    );
                    const notApplicable = item.categoryCoverage.reduce(
                      (total, category) => total + category.notApplicableCount,
                      0,
                    );
                    return (
                      <tr
                        aria-selected={
                          selectedAcceptance?.globalId === item.globalId
                        }
                        className="tooling-acceptance__lineage-row"
                        key={item.globalId}
                      >
                        <td data-language-exempt="business-data">
                          {set?.physicalSerial ?? item.toolingSetGlobalId}
                        </td>
                        <td data-language-exempt="identifier">
                          {t("Revision {{version}}", {
                            version: formatNumber(
                              locale,
                              item.acceptanceVersion,
                              0,
                            ),
                          })}
                        </td>
                        <td>{formatNumber(locale, recorded, 0)}</td>
                        <td>{formatNumber(locale, missing, 0)}</td>
                        <td>{formatNumber(locale, notApplicable, 0)}</td>
                        <td>
                          <div className="table-actions">
                            <Button
                              disabled={processing}
                              onClick={() => {
                                setSelectedAcceptanceId(item.globalId);
                              }}
                              visual="secondary"
                            >
                              {t("Inspect")}
                            </Button>
                            <Button
                              disabled={!canRecord || processing}
                              onClick={(event) => {
                                openAcceptance(
                                  event.currentTarget,
                                  item.toolingSetGlobalId,
                                  item,
                                );
                              }}
                              visual="secondary"
                            >
                              {t("Append Revision")}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state" role="status">
              <strong>
                {t("No acceptance evidence Revision has been recorded.")}
              </strong>
              <span>
                {t(
                  "Start with a physical Set that has an exact Tooling Revision binding.",
                )}
              </span>
            </div>
          )}
          {boundSets.length ? (
            <div className="tooling-acceptance__start-actions">
              {boundSets.map((item) => (
                <Button
                  disabled={!canRecord || processing}
                  key={item.globalId}
                  onClick={(event) => {
                    openAcceptance(event.currentTarget, item.globalId, null);
                  }}
                  visual="secondary"
                >
                  {t("Record evidence for {{serial}}", {
                    serial: item.physicalSerial,
                  })}
                </Button>
              ))}
            </div>
          ) : (
            <p>
              {t("No physical Set has an exact Tooling Revision binding yet.")}
            </p>
          )}
        </Panel>

        <Panel title={t("Acceptance truth inspector")}>
          <div
            aria-label={t("Acceptance truth inspector")}
            className="tooling-acceptance__inspector-scroll"
            tabIndex={0}
          >
            {selectedAcceptance ? (
              <>
                <DefinitionList
                  rows={[
                    {
                      label: t("Stable acceptance identity"),
                      value: selectedAcceptance.acceptanceGlobalId,
                      exempt: "identifier",
                    },
                    {
                      label: t("Evidence Revision"),
                      value: formatNumber(
                        locale,
                        selectedAcceptance.acceptanceVersion,
                        0,
                      ),
                    },
                    {
                      label: t("Tooling Revision"),
                      value: formatNumber(
                        locale,
                        selectedAcceptance.toolingRevisionNumber,
                        0,
                      ),
                    },
                    {
                      label: t("Recorded by"),
                      value: selectedAcceptance.createdByUserId,
                      exempt: "business-data",
                    },
                    {
                      label: t("Recorded at"),
                      value: formatDateTime(
                        locale,
                        selectedAcceptance.createdAt,
                      ),
                    },
                    {
                      label: t("Snapshot hash"),
                      value: selectedAcceptance.snapshotHash,
                      exempt: "identifier",
                    },
                  ]}
                />
                <div className="tooling-acceptance__coverage">
                  {selectedAcceptance.categoryCoverage.map((item) => (
                    <div
                      className="tooling-acceptance__coverage-row"
                      key={item.category}
                    >
                      <strong>{categoryLabel(t, item.category)}</strong>
                      <span className="tooling-acceptance__coverage-summary">
                        {t(
                          "{{recorded}} recorded · {{missing}} missing · {{notApplicable}} not applicable",
                          {
                            missing: formatNumber(locale, item.missingCount, 0),
                            notApplicable: formatNumber(
                              locale,
                              item.notApplicableCount,
                              0,
                            ),
                            recorded: formatNumber(
                              locale,
                              item.recordedCount,
                              0,
                            ),
                          },
                        )}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="tooling-acceptance__related-counts">
                  <span>
                    {t("Asset actions: {{count}}", {
                      count: formatNumber(
                        locale,
                        selectedAcceptance.assetActions.length,
                        0,
                      ),
                    })}
                  </span>
                  <span>
                    {t("Spare recommendations: {{count}}", {
                      count: formatNumber(
                        locale,
                        selectedAcceptance.spareRecommendations.length,
                        0,
                      ),
                    })}
                  </span>
                  <span>
                    {t("Repair records: {{count}}", {
                      count: formatNumber(
                        locale,
                        selectedAcceptance.repairs.length,
                        0,
                      ),
                    })}
                  </span>
                </div>
              </>
            ) : (
              <p>
                {t(
                  "Select an acceptance evidence Revision to inspect exact provenance.",
                )}
              </p>
            )}
          </div>
        </Panel>
      </div>

      <div className="tooling-acceptance__asset-grid">
        <Panel title={t("Mock Asset request preparation")}>
          <div className="tooling-acceptance__axis-grid">
            {(
              [
                [t("Target mode"), t("Mock")],
                [t("Request state"), t("Draft")],
                [t("Input validation"), t("Validated Mock")],
                [t("Business approval"), t("Unavailable")],
                [t("Dispatch"), t("Prohibited")],
                [t("Target result"), t("Not requested")],
              ] as const
            ).map(([label, state]) => (
              <div className="tooling-acceptance__axis" key={label}>
                <span className="tooling-acceptance__axis-label">{label}</span>
                <strong>{state}</strong>
              </div>
            ))}
          </div>
          {latestAcceptances.length ? (
            <label>
              <span>{t("Acceptance evidence Revision")}</span>
              <Select
                disabled={processing}
                onChange={(event) => {
                  setSelectedAcceptanceId(event.currentTarget.value);
                  setAcknowledged(false);
                }}
                value={selectedAcceptance?.globalId ?? ""}
              >
                {latestAcceptances.map((item) => {
                  const set = value.sets.items.find(
                    (candidate) =>
                      candidate.globalId === item.toolingSetGlobalId,
                  );
                  return (
                    <option key={item.globalId} value={item.globalId}>
                      {set?.physicalSerial} ·{" "}
                      {t("Revision {{version}}", {
                        version: formatNumber(
                          locale,
                          item.acceptanceVersion,
                          0,
                        ),
                      })}
                    </option>
                  );
                })}
              </Select>
            </label>
          ) : null}
          <label className="tooling-acceptance__acknowledgement">
            <input
              checked={acknowledged}
              disabled={!canPrepareMock || processing}
              onChange={(event) => {
                setAcknowledged(event.currentTarget.checked);
              }}
              type="checkbox"
            />
            <span>
              {t(
                "I confirm this only validates a local Mock draft. It does not approve Tooling, contact ERPNext or create an Asset.",
              )}
            </span>
          </label>
          <Button
            disabled={!canPrepareMock || !acknowledged || processing}
            onClick={submitMockRequest}
          >
            {t("Prepare Mock Asset request")}
          </Button>
          <small className="tooling-acceptance__note">
            {t(
              "This command cannot approve Tooling, dispatch a request, contact ERPNext or create a formal Asset.",
            )}
          </small>
        </Panel>

        <Panel title={t("ERPNext Asset projection")}>
          <div
            className="tooling-acceptance__projection-unavailable"
            role="status"
          >
            <SemanticStatus label={t("Unavailable")} tone="warning" />
            <strong>
              {t("Formal Asset mapping has not been observed from ERPNext.")}
            </strong>
            <span className="tooling-acceptance__projection-detail">
              {t(
                "Mapping cardinality is zero or one formal Asset per physical Set.",
              )}
            </span>
            <span className="tooling-acceptance__projection-detail">
              {t(
                "ERPNext remains the only editable system for Asset and location truth.",
              )}
            </span>
          </div>
        </Panel>
      </div>

      <Panel title={t("Prepared Mock request audit")}>
        {value.requests.items.length ? (
          <div
            aria-label={t("Prepared Mock request audit")}
            className="table-scroll"
            tabIndex={0}
          >
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("Request")}</th>
                  <th>{t("Physical Set")}</th>
                  <th>{t("Validation")}</th>
                  <th>{t("Dispatch")}</th>
                  <th>{t("Created at")}</th>
                </tr>
              </thead>
              <tbody>
                {value.requests.items.map((item) => (
                  <tr key={item.globalId}>
                    <td data-language-exempt="identifier">{item.globalId}</td>
                    <td data-language-exempt="business-data">
                      {item.requestInput.toolingSetPhysicalSerial}
                    </td>
                    <td>{t("Validated Mock")}</td>
                    <td>{t("Prohibited")}</td>
                    <td>{formatDateTime(locale, item.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>{t("No local Mock Asset request has been prepared.")}</p>
        )}
      </Panel>

      {draft ? (
        <Panel
          title={
            draft.acceptanceGlobalId
              ? t("Append acceptance evidence Revision")
              : t("Record acceptance evidence")
          }
        >
          <form
            className="tooling-acceptance__editor"
            onSubmit={(event) => {
              event.preventDefault();
              submitAcceptance();
            }}
          >
            <div className="tooling-acceptance__editor-meta">
              <label>
                <span>{t("Physical Tooling Set")}</span>
                <Select disabled value={draft.setId}>
                  {value.sets.items.map((item) => (
                    <option key={item.globalId} value={item.globalId}>
                      {item.physicalSerial}
                    </option>
                  ))}
                </Select>
              </label>
              <label>
                <span>{t("Append reason")}</span>
                <TextInput
                  disabled={processing}
                  onChange={(event) => {
                    setDraft({ ...draft, reason: event.currentTarget.value });
                  }}
                  value={draft.reason}
                />
              </label>
            </div>
            <div className="tooling-acceptance__checklist">
              {draft.checklist.map((item, index) => (
                <fieldset key={item.category}>
                  <legend>{categoryLabel(t, item.category)}</legend>
                  <label>
                    <span>{t("Evidence disposition")}</span>
                    <Select
                      disabled={processing}
                      onChange={(event) => {
                        const checklist = [...draft.checklist];
                        checklist[index] = {
                          ...item,
                          disposition: event.currentTarget
                            .value as ToolingEvidenceDisposition,
                        };
                        setDraft({ ...draft, checklist });
                      }}
                      value={item.disposition}
                    >
                      {(
                        [
                          "evidence_recorded",
                          "evidence_missing",
                          "not_applicable_asserted",
                        ] as const
                      ).map((disposition) => (
                        <option key={disposition} value={disposition}>
                          {dispositionLabel(t, disposition)}
                        </option>
                      ))}
                    </Select>
                  </label>
                  {item.disposition === "evidence_recorded" ? (
                    <div className="tooling-acceptance__file-grid">
                      {(
                        [
                          ["fileRevisionGlobalId", t("File Revision identity")],
                          [
                            "fileOptimisticVersion",
                            t("File optimistic version"),
                          ],
                          ["frappeContentHash", t("Frappe content hash")],
                          ["sha256", t("SHA-256")],
                        ] as const
                      ).map(([field, label]) => (
                        <label key={field}>
                          <span>{label}</span>
                          <TextInput
                            disabled={processing}
                            onChange={(event) => {
                              const checklist = [...draft.checklist];
                              checklist[index] = {
                                ...item,
                                [field]: event.currentTarget.value,
                              };
                              setDraft({ ...draft, checklist });
                            }}
                            value={item[field]}
                          />
                        </label>
                      ))}
                    </div>
                  ) : null}
                  {item.disposition === "not_applicable_asserted" ? (
                    <label>
                      <span>{t("Exact not-applicable reason")}</span>
                      <TextInput
                        disabled={processing}
                        onChange={(event) => {
                          const checklist = [...draft.checklist];
                          checklist[index] = {
                            ...item,
                            note: event.currentTarget.value,
                          };
                          setDraft({ ...draft, checklist });
                        }}
                        value={item.note}
                      />
                    </label>
                  ) : null}
                </fieldset>
              ))}
            </div>
            {formError ? (
              <p className="form-error" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="form-actions">
              <Button disabled={!canRecord || processing} type="submit">
                {draft.acceptanceGlobalId
                  ? t("Append evidence Revision")
                  : t("Record evidence Revision")}
              </Button>
              <Button
                disabled={processing}
                onClick={() => {
                  setDraft(null);
                  setFormError(null);
                  editorTrigger.current?.focus();
                }}
                type="button"
                visual="secondary"
              >
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}
    </section>
  );
}
