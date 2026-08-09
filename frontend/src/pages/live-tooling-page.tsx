import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { DocumentDataSource } from "../api/document-data-source";
import type {
  CreateToolingApplicabilityCommand,
  ToolingCockpitViewModel,
  ToolingDataSource,
  ToolingDownstreamReason,
  ToolingRequirementKind,
} from "../api/tooling-data-source";
import { ToolingRequestCancelledError } from "../api/tooling-data-source";
import type { ToolingListDataSource } from "../api/tooling-list-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import {
  DockedInspector,
  ObjectHeader,
  SectionAnchors,
} from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { ToolingListWorkspace } from "../components/tooling-list-workspace";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import { formatDate, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";
import ToolingManufacturingWorkspace from "./tooling-manufacturing-workspace";
import ToolingAcceptanceAssetWorkspace from "./tooling-acceptance-asset-workspace";
import ToolingEngineeringControlsWorkspace from "./tooling-engineering-controls-workspace";
import ToolingRevisionWorkspace from "./tooling-revision-workspace";
import ToolingSetWorkspace from "./tooling-set-workspace";

type ResourceState =
  | { kind: "loading" }
  | { kind: "loaded"; value: ToolingCockpitViewModel }
  | { kind: "failed"; failure: RequestFailure };
type EditorKind =
  | "part"
  | "revision"
  | "requirement"
  | "master"
  | "applicability";
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

interface EditorState {
  kind: EditorKind;
  title: string;
  revisionLabel: string;
  reason: string;
  requirementKind: ToolingRequirementKind;
  targetPartRevisionId: string;
  targetDate: string;
  partId: string;
  masterId: string;
  relationshipId: string;
  effectiveFrom: string;
  effectiveTo: string;
}

const source = {
  editableIn: "NPI_ONE" as const,
  sourceSystem: "NPI_ONE" as const,
  syncState: "local" as const,
};

function newEditor(kind: EditorKind): EditorState {
  return {
    kind,
    title: "",
    revisionLabel: "",
    reason: "",
    requirementKind: "new_tool",
    targetPartRevisionId: "",
    targetDate: "",
    partId: "",
    masterId: "",
    relationshipId: "",
    effectiveFrom: new Date().toISOString().slice(0, 10),
    effectiveTo: "",
  };
}

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function requirementKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: ToolingRequirementKind,
): string {
  switch (kind) {
    case "new_tool":
      return t("New Tooling");
    case "customer_owned_intake":
      return t("Customer-owned Tooling intake");
    case "copy_or_additional_set":
      return t("Copy or additional Set");
    case "modification":
      return t("Tooling modification");
    case "repair":
      return t("Tooling repair");
    case "capacity_need":
      return t("Capacity need");
  }
}

function downstreamLabel(
  t: ReturnType<typeof useI18n>["t"],
  reason: ToolingDownstreamReason,
): string {
  switch (reason) {
    case "lifecycle_policy_unavailable":
      return t("Lifecycle policy is not approved.");
    case "tooling_revision_not_delivered":
      return t("Tooling Revision is not delivered yet.");
    case "physical_set_not_delivered":
      return t("Physical Tooling Set is not delivered yet.");
    case "trial_not_delivered":
      return t("Trial truth is not delivered yet.");
    case "erp_projection_unavailable":
      return t("ERPNext projection is unavailable.");
  }
}

function editorLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: EditorKind,
): string {
  switch (kind) {
    case "part":
      return t("Create Part and initial Revision");
    case "revision":
      return t("Create immutable Part Revision");
    case "requirement":
      return t("Record Tooling requirement");
    case "master":
      return t("Create logical Tooling Master");
    case "applicability":
      return t("Append Tooling applicability");
  }
}

function LoadingSurface(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section
      aria-busy="true"
      aria-label={t("Loading Tooling workspace")}
      className="workspace-resource-state workspace-resource-state--loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">{t("Loading Tooling workspace")}</span>
    </section>
  );
}

export default function LiveToolingPage({
  dataSource,
  documentDataSource,
  projectId,
  masterId,
  navigate,
  reportWorkspaceDirty,
  toolingListDataSource,
}: {
  dataSource: ToolingDataSource;
  documentDataSource?: DocumentDataSource | undefined;
  projectId: string;
  masterId: string | null;
  navigate: (target: string) => void;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  toolingListDataSource?: ToolingListDataSource | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [selectedMasterId, setSelectedMasterId] = useState<string | null>(
    masterId,
  );
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const firstEditorControl = useRef<HTMLElement | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const latestCommand = useRef<(() => void) | null>(null);
  const cockpit = resource.kind === "loaded" ? resource.value : null;
  const selectedMaster =
    cockpit?.masters.find((item) => item.globalId === selectedMasterId) ??
    cockpit?.masters[0] ??
    null;
  const selectedApplicability = useMemo(
    () =>
      cockpit?.applicability.filter(
        (item) => item.toolingMasterGlobalId === selectedMaster?.globalId,
      ) ?? [],
    [cockpit?.applicability, selectedMaster?.globalId],
  );
  const allowedEditors = useMemo(() => {
    if (!cockpit) return [];
    const values: EditorKind[] = [];
    if (cockpit.permissions.createPart) {
      values.push("part");
      if (cockpit.parts.length) values.push("revision");
    }
    if (cockpit.permissions.createRequirement) values.push("requirement");
    if (cockpit.permissions.createMaster) values.push("master");
    if (
      cockpit.permissions.createApplicability &&
      cockpit.parts.length &&
      cockpit.masters.length
    ) {
      values.push("applicability");
    }
    return values;
  }, [cockpit]);

  useEffect(() => {
    const controller = new AbortController();
    const request = masterId
      ? dataSource.loadMaster(projectId, masterId, controller.signal)
      : dataSource.loadCockpit(projectId, controller.signal);
    void request
      .then((value) => {
        if (controller.signal.aborted) return;
        setResource({ kind: "loaded", value });
        setSelectedMasterId(
          (current) => current ?? value.masters[0]?.globalId ?? null,
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ToolingRequestCancelledError
        ) {
          return;
        }
        setResource({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, masterId, projectId]);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!editor) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity:
        selectedMaster?.globalId ?? `${projectId}:new-tooling-record`,
      version: "unsaved-tooling-context",
      returnFocusTarget: () =>
        firstEditorControl.current ??
        document.getElementById("tooling-add-record"),
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [editor, projectId, reportWorkspaceDirty, selectedMaster?.globalId]);

  const closeEditor = useCallback((): void => {
    setEditor(null);
    setFormError(null);
    setCommand({ kind: "idle" });
    const target = returnFocus.current;
    globalThis.queueMicrotask(() => target?.focus());
  }, []);

  const openEditor = (kind: EditorKind, trigger: HTMLElement): void => {
    const next = newEditor(kind);
    if (cockpit?.parts[0]) {
      next.partId = cockpit.parts[0].globalId;
      next.targetPartRevisionId = cockpit.parts[0].currentRevision.globalId;
      next.title = kind === "revision" ? cockpit.parts[0].title : "";
    }
    if (selectedMaster) next.masterId = selectedMaster.globalId;
    returnFocus.current = trigger;
    setFormError(null);
    setCommand({ kind: "idle" });
    setEditor(next);
    globalThis.queueMicrotask(() => firstEditorControl.current?.focus());
  };

  const acceptCommand = useCallback((value: ToolingCockpitViewModel): void => {
    setResource({ kind: "loaded", value });
    setSelectedMasterId((current) =>
      current && value.masters.some((item) => item.globalId === current)
        ? current
        : (value.masters.at(-1)?.globalId ?? null),
    );
    setEditor(null);
    setFormError(null);
    setCommand({ kind: "idle" });
    const target = returnFocus.current;
    globalThis.queueMicrotask(() => target?.focus());
  }, []);

  const runCommand = useCallback(
    (
      label: string,
      operation: (signal: AbortSignal) => Promise<ToolingCockpitViewModel>,
    ): void => {
      const execute = (): void => {
        const controller = new AbortController();
        setCommand({ kind: "processing", label });
        void operation(controller.signal)
          .then(acceptCommand)
          .catch((error: unknown) => {
            if (
              controller.signal.aborted ||
              error instanceof ToolingRequestCancelledError
            ) {
              return;
            }
            setCommand({ kind: "failed", failure: toRequestFailure(error) });
          });
      };
      latestCommand.current = execute;
      execute();
    },
    [acceptCommand],
  );

  const submitEditor = (): void => {
    if (!cockpit || !editor || !sessionCommandContext) return;
    if (!editor.reason.trim() && editor.kind !== "master") {
      setFormError(t("Enter a reason before submitting this Tooling command."));
      return;
    }
    const context = (prefix: string) => {
      const idempotencyKey = `${prefix}-${globalThis.crypto.randomUUID()}`;
      return (signal: AbortSignal) => ({
        ...sessionCommandContext,
        idempotencyKey,
        signal,
      });
    };
    if (editor.kind === "part") {
      if (!editor.title.trim() || !editor.revisionLabel.trim()) {
        setFormError(t("Enter the Part title and initial Revision label."));
        return;
      }
      const commandContext = context("tooling-part");
      runCommand(t("Creating Part and initial Revision"), (signal) =>
        dataSource.createPart(
          projectId,
          {
            reason: editor.reason.trim(),
            revisionLabel: editor.revisionLabel.trim(),
            title: editor.title.trim(),
          },
          commandContext(signal),
        ),
      );
      return;
    }
    if (editor.kind === "revision") {
      const part = cockpit.parts.find(
        (item) => item.globalId === editor.partId,
      );
      if (!part || !editor.title.trim() || !editor.revisionLabel.trim()) {
        setFormError(
          t("Select the Part and enter the successor Revision details."),
        );
        return;
      }
      const commandContext = context("tooling-part-revision");
      runCommand(t("Creating immutable Part Revision"), (signal) =>
        dataSource.createPartRevision(
          projectId,
          part.globalId,
          {
            expectedVersion: part.version,
            reason: editor.reason.trim(),
            revisionLabel: editor.revisionLabel.trim(),
            title: editor.title.trim(),
          },
          commandContext(signal),
        ),
      );
      return;
    }
    if (editor.kind === "requirement") {
      if (!editor.title.trim()) {
        setFormError(t("Enter the Tooling requirement title."));
        return;
      }
      const commandContext = context("tooling-requirement");
      runCommand(t("Recording Tooling requirement"), (signal) =>
        dataSource.createRequirement(
          projectId,
          {
            kind: editor.requirementKind,
            reason: editor.reason.trim(),
            title: editor.title.trim(),
            ...(editor.targetDate ? { targetDate: editor.targetDate } : {}),
            ...(editor.targetPartRevisionId
              ? { targetPartRevisionGlobalId: editor.targetPartRevisionId }
              : {}),
          },
          commandContext(signal),
        ),
      );
      return;
    }
    if (editor.kind === "master") {
      if (!editor.title.trim()) {
        setFormError(t("Enter the logical Tooling Master title."));
        return;
      }
      const commandContext = context("tooling-master");
      runCommand(t("Creating logical Tooling Master"), (signal) =>
        dataSource.createMaster(
          projectId,
          { title: editor.title.trim() },
          commandContext(signal),
        ),
      );
      return;
    }
    const part = cockpit.parts.find((item) => item.globalId === editor.partId);
    const master = cockpit.masters.find(
      (item) => item.globalId === editor.masterId,
    );
    if (!part || !master || !editor.effectiveFrom) {
      setFormError(
        t("Select the exact Master, Part Revision and effective date."),
      );
      return;
    }
    const predecessor = cockpit.applicability
      .filter((item) => item.relationshipGlobalId === editor.relationshipId)
      .sort((left, right) => right.version - left.version)[0];
    const applicability: CreateToolingApplicabilityCommand = {
      effectiveFrom: editor.effectiveFrom,
      partRevisionGlobalId: part.currentRevision.globalId,
      reason: editor.reason.trim(),
      toolingMasterGlobalId: master.globalId,
      ...(editor.effectiveTo ? { effectiveTo: editor.effectiveTo } : {}),
      ...(predecessor
        ? {
            expectedVersion: predecessor.version,
            relationshipGlobalId: predecessor.relationshipGlobalId,
          }
        : {}),
    };
    const commandContext = context("tooling-applicability");
    runCommand(t("Appending Tooling applicability"), (signal) =>
      dataSource.createApplicability(
        projectId,
        applicability,
        commandContext(signal),
      ),
    );
  };

  if (resource.kind === "loading") return <LoadingSurface />;
  if (resource.kind === "failed") {
    return (
      <article className="page page--object">
        <Panel title={t("Tooling workspace unavailable")}>
          <RequestFailurePanel failure={resource.failure} />
          <div className="detail-actions">
            {canRetry(resource.failure) ? (
              <Button
                onClick={() => {
                  setResource({ kind: "loading" });
                  setAttempt((current) => current + 1);
                }}
              >
                {t("Retry")}
              </Button>
            ) : null}
            <Button
              onClick={() => {
                navigate(`/projects/${projectId}`);
              }}
            >
              {t("Return to project")}
            </Button>
          </div>
        </Panel>
      </article>
    );
  }
  if (!cockpit) return <LoadingSurface />;

  const empty =
    cockpit.masters.length === 0 &&
    cockpit.parts.length === 0 &&
    cockpit.requirements.length === 0 &&
    cockpit.applicability.length === 0;
  const processing = command.kind === "processing";
  const canMutate = allowedEditors.length > 0 && sessionCommandContext !== null;

  return (
    <article className="page page--object tooling-live">
      <ObjectHeader
        code={cockpit.project.businessCode}
        metadata={
          <span>
            {t("Logical Masters")}:{" "}
            {formatNumber(locale, cockpit.masters.length, 0)} · {t("Parts")}:{" "}
            {formatNumber(locale, cockpit.parts.length, 0)} ·{" "}
            {t("Applicability relationships")}:{" "}
            {formatNumber(locale, cockpit.applicability.length, 0)}
          </span>
        }
        name={cockpit.project.title}
        primaryAction={
          allowedEditors.length
            ? {
                disabled: !canMutate || processing,
                id: "tooling-add-record",
                label: t("Add Tooling record"),
                onClick: () => {
                  const trigger = document.getElementById("tooling-add-record");
                  if (trigger) openEditor(allowedEditors[0] ?? "part", trigger);
                },
              }
            : undefined
        }
        secondaryAction={
          <Button
            icon="upload"
            onClick={() => {
              navigate(`/projects/${projectId}/tooling?workspace=import`);
            }}
          >
            {t("Open Tooling List import")}
          </Button>
        }
        source={source}
        status={
          <SemanticStatus
            label={t("Identity and applicability foundation")}
            tone="info"
          />
        }
      />
      <SectionAnchors
        sections={[
          ...(toolingListDataSource
            ? [{ id: "tooling-list-workspace", label: t("Tooling List") }]
            : []),
          { id: "tooling-live-objects", label: t("Tooling objects") },
          {
            id: "tooling-live-applicability",
            label: t("Applicability and Part Revisions"),
          },
          {
            id: "tooling-live-sets",
            label: t("Physical Tooling Sets and intake"),
          },
          {
            id: "tooling-manufacturing-workspace",
            label: t("Manufacturing and supplier"),
          },
          {
            id: "tooling-engineering-controls-workspace",
            label: t("Engineering controls"),
          },
          { id: "tooling-live-inspector", label: t("Tooling truth inspector") },
        ]}
      />
      {!sessionCommandContext && allowedEditors.length ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Tooling data is read only in this session.")}</span>
          <span>
            {t(
              "Session verification is required before a Tooling command can be submitted.",
            )}
          </span>
        </div>
      ) : null}
      {allowedEditors.length === 0 ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>
            {t(
              "Tooling data is read only because this session has no mutation capability.",
            )}
          </span>
          <span>
            {t(
              "The server, not the browser, controls each available Tooling action.",
            )}
          </span>
        </div>
      ) : null}
      {empty ? (
        <div className="empty-state" role="status">
          <strong>
            {t("No Tooling identity has been recorded for this Project.")}
          </strong>
          <span>
            {t(
              "Create distinct Part, Requirement, Master and Applicability records without inventing lifecycle or ERPNext truth.",
            )}
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
              onClick={() => latestCommand.current?.()}
            >
              {t("Retry exact command")}
            </Button>
          ) : null}
        </div>
      ) : null}
      {toolingListDataSource ? (
        <ToolingListWorkspace
          dataSource={toolingListDataSource}
          key={projectId}
          navigate={navigate}
          projectId={projectId}
          selectedMasterId={selectedMaster?.globalId ?? masterId}
        />
      ) : null}
      <div className="engineering-layout tooling-live__layout">
        <Panel id="tooling-live-objects" title={t("Tooling objects")}>
          <ul className="object-tree tooling-live__tree">
            {cockpit.masters.map((item) => (
              <li key={item.globalId}>
                <button
                  aria-current={
                    selectedMaster?.globalId === item.globalId
                      ? "true"
                      : undefined
                  }
                  className="tooling-live__tree-control"
                  onClick={() => {
                    setSelectedMasterId(item.globalId);
                    navigate(`/projects/${projectId}/tooling/${item.globalId}`);
                  }}
                  type="button"
                >
                  <SemanticStatus
                    label={t("Logical Tooling Master")}
                    tone="neutral"
                  />
                  <strong data-language-exempt="business-data">
                    {item.title}
                  </strong>
                </button>
              </li>
            ))}
            {cockpit.parts.map((item) => (
              <li key={item.globalId}>
                <SemanticStatus label={t("Engineering Part")} tone="info" />
                <strong data-language-exempt="business-data">
                  {item.title}
                </strong>
                <small data-language-exempt="identifier">
                  {item.currentRevision.revisionLabel}
                </small>
              </li>
            ))}
            {cockpit.requirements.map((item) => (
              <li key={item.globalId}>
                <SemanticStatus
                  label={t("Tooling requirement")}
                  tone="neutral"
                />
                <strong data-language-exempt="business-data">
                  {item.title}
                </strong>
                <small>{requirementKindLabel(t, item.kind)}</small>
              </li>
            ))}
          </ul>
        </Panel>
        <div className="tooling-live__center">
          <Panel
            id="tooling-live-applicability"
            title={t("Applicability and Part Revisions")}
          >
            {cockpit.applicability.length ? (
              <div
                aria-label={t("Applicability and Part Revisions")}
                className="table-scroll"
                tabIndex={0}
              >
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("Tooling Master")}</th>
                      <th>{t("Part Revision")}</th>
                      <th>{t("Applicability version")}</th>
                      <th>{t("Effective from")}</th>
                      <th>{t("Effective to")}</th>
                      <th>{t("Product and model context")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cockpit.applicability.map((item) => {
                      const master = cockpit.masters.find(
                        (candidate) =>
                          candidate.globalId === item.toolingMasterGlobalId,
                      );
                      return (
                        <tr key={item.globalId}>
                          <td data-language-exempt="business-data">
                            {master?.title}
                          </td>
                          <td data-language-exempt="identifier">
                            {item.part.revisionLabel}
                          </td>
                          <td>{formatNumber(locale, item.version, 0)}</td>
                          <td>
                            <time dateTime={item.effectiveFrom}>
                              {formatDate(locale, item.effectiveFrom)}
                            </time>
                          </td>
                          <td>
                            {item.effectiveTo ? (
                              <time dateTime={item.effectiveTo}>
                                {formatDate(locale, item.effectiveTo)}
                              </time>
                            ) : (
                              t("Open ended")
                            )}
                          </td>
                          <td>
                            {item.product || item.model ? (
                              <span data-language-exempt="business-data">
                                {[
                                  item.product?.sourceObjectId,
                                  item.model?.sourceObjectId,
                                ]
                                  .filter(Boolean)
                                  .join(" · ")}
                              </span>
                            ) : (
                              t("Project and exact Part Revision only")
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p>{t("No Tooling applicability has been recorded.")}</p>
            )}
          </Panel>
          <Panel title={t("Tooling requirements")}>
            {cockpit.requirements.length ? (
              <div
                aria-label={t("Tooling requirements")}
                className="table-scroll"
                tabIndex={0}
              >
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("Requirement")}</th>
                      <th>{t("Kind")}</th>
                      <th>{t("Exact Part Revision")}</th>
                      <th>{t("Target date")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cockpit.requirements.map((item) => (
                      <tr key={item.globalId}>
                        <td data-language-exempt="business-data">
                          {item.title}
                        </td>
                        <td>{requirementKindLabel(t, item.kind)}</td>
                        <td
                          data-language-exempt={
                            item.targetPartRevisionGlobalId
                              ? "identifier"
                              : undefined
                          }
                        >
                          {item.targetPartRevisionGlobalId ?? t("Not linked")}
                        </td>
                        <td>
                          {item.targetDate ? (
                            <time dateTime={item.targetDate}>
                              {formatDate(locale, item.targetDate)}
                            </time>
                          ) : (
                            t("Not set")
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p>{t("No Tooling requirement has been recorded.")}</p>
            )}
          </Panel>
        </div>
        <DockedInspector
          id="tooling-live-inspector"
          title={t("Tooling truth inspector")}
        >
          {selectedMaster ? (
            <DefinitionList
              rows={[
                {
                  label: t("Logical Master"),
                  value: selectedMaster.title,
                  exempt: "business-data",
                },
                {
                  label: t("Master identity"),
                  value: selectedMaster.globalId,
                  exempt: "identifier",
                },
                {
                  label: t("Originating Project"),
                  value: selectedMaster.originatingProjectGlobalId,
                  exempt: "identifier",
                },
                {
                  label: t("Snapshot hash"),
                  value: selectedMaster.snapshotHash,
                  exempt: "identifier",
                },
                {
                  label: t("Applicability relationships"),
                  value: formatNumber(locale, selectedApplicability.length, 0),
                },
              ]}
            />
          ) : (
            <p>
              {t(
                "Select or create a logical Tooling Master to inspect exact identity truth.",
              )}
            </p>
          )}
          <div className="tooling-live__downstream">
            <strong>{t("Downstream capability truth")}</strong>
            {(
              [
                ["lifecycle", cockpit.downstream.lifecycle],
                ["trial", cockpit.downstream.trial],
                ["erp", cockpit.downstream.erp],
              ] as const
            ).map(([key, capability]) => (
              <div className="tooling-live__downstream-row" key={key}>
                <SemanticStatus label={t("Unavailable")} tone="warning" />
                <span>{downstreamLabel(t, capability.reasonCode)}</span>
              </div>
            ))}
            <div className="tooling-live__downstream-row">
              <SemanticStatus
                label={
                  cockpit.downstream.revision.state === "available"
                    ? t("Available")
                    : t("Unavailable")
                }
                tone={
                  cockpit.downstream.revision.state === "available"
                    ? "success"
                    : "warning"
                }
              />
              <span>
                {cockpit.downstream.revision.state === "available"
                  ? t("Tooling Revision workspace is available.")
                  : downstreamLabel(t, cockpit.downstream.revision.reasonCode)}
              </span>
            </div>
          </div>
          <small>
            {t(
              "No lifecycle, Tooling Revision, Trial or ERPNext success is inferred by this workspace.",
            )}
          </small>
        </DockedInspector>
      </div>
      {selectedMaster && cockpit.downstream.revision.state === "available" ? (
        <ToolingRevisionWorkspace
          applicability={selectedApplicability}
          dataSource={dataSource}
          key={`revision-${selectedMaster.globalId}`}
          masterId={selectedMaster.globalId}
          parts={cockpit.parts}
          projectId={projectId}
          reportWorkspaceDirty={reportWorkspaceDirty}
        />
      ) : null}
      {selectedMaster ? (
        <ToolingManufacturingWorkspace
          dataSource={dataSource}
          key={`manufacturing-${selectedMaster.globalId}`}
          masterId={selectedMaster.globalId}
          projectId={projectId}
          reportWorkspaceDirty={reportWorkspaceDirty}
        />
      ) : null}
      {selectedMaster ? (
        <ToolingEngineeringControlsWorkspace
          dataSource={dataSource}
          key={`engineering-controls-${selectedMaster.globalId}`}
          masterId={selectedMaster.globalId}
          projectId={projectId}
          reportWorkspaceDirty={reportWorkspaceDirty}
        />
      ) : null}
      {selectedMaster ? (
        <ToolingSetWorkspace
          dataSource={dataSource}
          documentDataSource={documentDataSource}
          key={selectedMaster.globalId}
          masterId={selectedMaster.globalId}
          projectId={projectId}
          revisionCapabilityAvailable={
            cockpit.downstream.revision.state === "available"
          }
          reportWorkspaceDirty={reportWorkspaceDirty}
          requirements={cockpit.requirements}
        />
      ) : null}
      {selectedMaster ? (
        <ToolingAcceptanceAssetWorkspace
          dataSource={dataSource}
          key={`acceptance-assets-${selectedMaster.globalId}`}
          master={selectedMaster}
          projectId={projectId}
          reportWorkspaceDirty={reportWorkspaceDirty}
        />
      ) : null}
      {editor ? (
        <Panel id="tooling-live-editor" title={editorLabel(t, editor.kind)}>
          <form
            className="ebom-form tooling-live__form"
            onSubmit={(event) => {
              event.preventDefault();
              submitEditor();
            }}
          >
            <label
              ref={(element) => {
                firstEditorControl.current = element;
              }}
            >
              <span>{t("Command")}</span>
              <Select
                disabled={processing}
                onChange={(event) => {
                  setEditor(newEditor(event.currentTarget.value as EditorKind));
                }}
                value={editor.kind}
              >
                {allowedEditors.map((kind) => (
                  <option key={kind} value={kind}>
                    {editorLabel(t, kind)}
                  </option>
                ))}
              </Select>
            </label>
            {editor.kind === "revision" ? (
              <label>
                <span>{t("Engineering Part")}</span>
                <Select
                  disabled={processing}
                  onChange={(event) => {
                    const part = cockpit.parts.find(
                      (item) => item.globalId === event.currentTarget.value,
                    );
                    setEditor({
                      ...editor,
                      partId: event.currentTarget.value,
                      title: part?.title ?? editor.title,
                    });
                  }}
                  value={editor.partId}
                >
                  {cockpit.parts.map((item) => (
                    <option
                      data-language-exempt="business-data"
                      key={item.globalId}
                      value={item.globalId}
                    >
                      {item.title}
                    </option>
                  ))}
                </Select>
              </label>
            ) : null}
            {editor.kind === "requirement" ? (
              <label>
                <span>{t("Requirement kind")}</span>
                <Select
                  disabled={processing}
                  onChange={(event) => {
                    setEditor({
                      ...editor,
                      requirementKind: event.currentTarget
                        .value as ToolingRequirementKind,
                    });
                  }}
                  value={editor.requirementKind}
                >
                  {(
                    [
                      "new_tool",
                      "customer_owned_intake",
                      "copy_or_additional_set",
                      "modification",
                      "repair",
                      "capacity_need",
                    ] as const
                  ).map((kind) => (
                    <option key={kind} value={kind}>
                      {requirementKindLabel(t, kind)}
                    </option>
                  ))}
                </Select>
              </label>
            ) : null}
            {editor.kind === "applicability" ? (
              <>
                <label>
                  <span>{t("Logical Tooling Master")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        masterId: event.currentTarget.value,
                      });
                    }}
                    value={editor.masterId}
                  >
                    {cockpit.masters.map((item) => (
                      <option
                        data-language-exempt="business-data"
                        key={item.globalId}
                        value={item.globalId}
                      >
                        {item.title}
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("Exact Part Revision")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        partId: event.currentTarget.value,
                      });
                    }}
                    value={editor.partId}
                  >
                    {cockpit.parts.map((item) => (
                      <option
                        data-language-exempt="business-data"
                        key={item.globalId}
                        value={item.globalId}
                      >
                        {item.title} · {item.currentRevision.revisionLabel}
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("Applicability relationship")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        relationshipId: event.currentTarget.value,
                      });
                    }}
                    value={editor.relationshipId}
                  >
                    <option value="">{t("New relationship")}</option>
                    {Array.from(
                      new Set(
                        cockpit.applicability.map(
                          (item) => item.relationshipGlobalId,
                        ),
                      ),
                    ).map((relationshipId) => (
                      <option
                        data-language-exempt="identifier"
                        key={relationshipId}
                        value={relationshipId}
                      >
                        {relationshipId}
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("Effective from")}</span>
                  <TextInput
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        effectiveFrom: event.currentTarget.value,
                      });
                    }}
                    required
                    type="date"
                    value={editor.effectiveFrom}
                  />
                </label>
                <label>
                  <span>{t("Effective to")}</span>
                  <TextInput
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        effectiveTo: event.currentTarget.value,
                      });
                    }}
                    type="date"
                    value={editor.effectiveTo}
                  />
                </label>
              </>
            ) : null}
            {editor.kind === "requirement" ? (
              <>
                <label>
                  <span>{t("Exact Part Revision")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        targetPartRevisionId: event.currentTarget.value,
                      });
                    }}
                    value={editor.targetPartRevisionId}
                  >
                    <option value="">{t("Not linked")}</option>
                    {cockpit.parts.map((item) => (
                      <option
                        data-language-exempt="business-data"
                        key={item.currentRevision.globalId}
                        value={item.currentRevision.globalId}
                      >
                        {item.title} · {item.currentRevision.revisionLabel}
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("Target date")}</span>
                  <TextInput
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        targetDate: event.currentTarget.value,
                      });
                    }}
                    type="date"
                    value={editor.targetDate}
                  />
                </label>
              </>
            ) : null}
            {editor.kind !== "applicability" ? (
              <label>
                <span>
                  {editor.kind === "revision" ? t("Part title") : t("Title")}
                </span>
                <TextInput
                  disabled={processing}
                  maxLength={140}
                  onChange={(event) => {
                    setEditor({ ...editor, title: event.currentTarget.value });
                  }}
                  required
                  value={editor.title}
                />
              </label>
            ) : null}
            {editor.kind === "part" || editor.kind === "revision" ? (
              <label>
                <span>{t("Revision label")}</span>
                <TextInput
                  disabled={processing}
                  maxLength={40}
                  onChange={(event) => {
                    setEditor({
                      ...editor,
                      revisionLabel: event.currentTarget.value,
                    });
                  }}
                  required
                  value={editor.revisionLabel}
                />
              </label>
            ) : null}
            {editor.kind !== "master" ? (
              <label className="ebom-form__wide">
                <span>{t("Reason")}</span>
                <TextInput
                  disabled={processing}
                  maxLength={500}
                  onChange={(event) => {
                    setEditor({ ...editor, reason: event.currentTarget.value });
                  }}
                  required
                  value={editor.reason}
                />
              </label>
            ) : null}
            {formError ? (
              <p className="ebom-form__wide form-error" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions ebom-form__wide">
              <Button
                disabled={processing || !sessionCommandContext}
                type="submit"
                visual="primary"
              >
                {editorLabel(t, editor.kind)}
              </Button>
              <Button disabled={processing} onClick={closeEditor} type="button">
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}
    </article>
  );
}
