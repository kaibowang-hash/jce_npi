import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  trialActionSeverities,
  trialPurposes,
  TrialRequestCancelledError,
  type CreatePlannedTrialRoundCommand,
  type CreateTrialPlanCommand,
  type CreateTrialPlanRevisionCommand,
  type GenerateTrialPlanActionsCommand,
  type TrialActionSeverity,
  type TrialCommandResult,
  type TrialDataSource,
  type TrialPlanDetail,
  type TrialPlanningWorkspace,
  type TrialPurpose,
  type TrialResourceProposalInput,
  type TrialRoundState,
} from "../api/trial-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import {
  DockedInspector,
  ObjectHeader,
  SectionAnchors,
} from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ResourceState =
  | { kind: "loading" }
  | { kind: "loaded"; value: TrialPlanningWorkspace }
  | { kind: "failed"; failure: RequestFailure };
type DetailState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; value: TrialPlanDetail }
  | { kind: "failed"; failure: RequestFailure };
type EditorKind =
  | "create_plan"
  | "revise_plan"
  | "create_round"
  | "generate_action";
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "succeeded"; label: string; replayed: boolean }
  | { kind: "failed"; failure: RequestFailure };

interface EditorState {
  kind: EditorKind;
  toolingMasterGlobalId: string;
  purpose: TrialPurpose;
  objective: string;
  plannedStartAt: string;
  plannedEndAt: string;
  machineSourceSystem: "NPI_ONE" | "ERPNEXT";
  machineSourceObjectId: string;
  machineLabel: string;
  materialSourceSystem: "NPI_ONE" | "ERPNEXT";
  materialSourceObjectId: string;
  materialLabel: string;
  materialQuantity: string;
  materialUnit: string;
  responsibleMemberGlobalIds: string;
  sampleQuantity: string;
  measurementPlanDescription: string;
  displayLabel: string;
  actionKey: string;
  actionTitle: string;
  actionDescription: string;
  actionResponsibleMemberGlobalId: string;
  actionDueAt: string;
  actionSeverity: TrialActionSeverity;
  actionBlocking: boolean;
  trialRoundGlobalId: string;
}

const source = {
  editableIn: "NPI_ONE" as const,
  sourceSystem: "NPI_ONE" as const,
  syncState: "local" as const,
};
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

function utcInput(value: string): string {
  return new Date(value).toISOString().slice(0, 16);
}

function utcInstant(value: string): string {
  return new Date(`${value}:00Z`).toISOString();
}

function memberIds(value: string): readonly string[] {
  return value
    .split(/[\s,;]+/u)
    .map((item) => item.trim())
    .filter(Boolean);
}

function purposeLabel(
  t: ReturnType<typeof useI18n>["t"],
  purpose: TrialPurpose,
): string {
  switch (purpose) {
    case "first_trial":
      return t("First Trial");
    case "tooling_change_verification":
      return t("Tooling change verification");
    case "design_verification":
      return t("Design verification");
    case "material_color_verification":
      return t("Material and color verification");
    case "capability_study":
      return t("Capability study");
    case "customer_sample":
      return t("Customer sample");
    case "other":
      return t("Other Trial purpose");
  }
}

function roundStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: TrialRoundState,
): string {
  switch (state) {
    case "planned":
      return t("Planned");
    case "prepared":
      return t("Prepared");
    case "running":
      return t("Running");
    case "analysis":
      return t("Analysis");
    case "submitted":
      return t("Submitted");
    case "approved":
      return t("Approved");
    case "rejected":
      return t("Rejected");
    case "cancelled":
      return t("Cancelled");
  }
}

function severityLabel(
  t: ReturnType<typeof useI18n>["t"],
  severity: TrialActionSeverity,
): string {
  switch (severity) {
    case "low":
      return t("Low");
    case "medium":
      return t("Medium");
    case "high":
      return t("High");
    case "critical":
      return t("Critical");
  }
}

function editorLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: EditorKind,
): string {
  switch (kind) {
    case "create_plan":
      return t("Create Trial Plan");
    case "revise_plan":
      return t("Append Trial Plan revision");
    case "create_round":
      return t("Create planned Trial Round");
    case "generate_action":
      return t("Generate governed action");
  }
}

function commandProcessingLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: EditorKind,
): string {
  switch (kind) {
    case "create_plan":
      return t("Creating Trial Plan");
    case "revise_plan":
      return t("Appending Trial Plan revision");
    case "create_round":
      return t("Creating planned Trial Round");
    case "generate_action":
      return t("Generating governed action");
  }
}

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function newEditor(
  kind: EditorKind,
  detail: TrialPlanDetail | null,
): EditorState {
  const revision = detail?.latestRevision ?? null;
  const machine = revision?.resources.find((item) => item.kind === "machine");
  const material = revision?.resources.find((item) => item.kind === "material");
  const now = new Date();
  const start = new Date(now.getTime() + 86_400_000);
  const end = new Date(start.getTime() + 14_400_000);
  return {
    kind,
    toolingMasterGlobalId: revision?.toolingMasterGlobalId ?? "",
    purpose: revision?.purpose ?? "first_trial",
    objective: revision?.objective ?? "",
    plannedStartAt: revision
      ? utcInput(revision.plannedStartAt)
      : utcInput(start.toISOString()),
    plannedEndAt: revision
      ? utcInput(revision.plannedEndAt)
      : utcInput(end.toISOString()),
    machineSourceSystem: machine?.sourceSystem ?? "ERPNEXT",
    machineSourceObjectId: machine?.sourceObjectId ?? "",
    machineLabel: machine?.label ?? "",
    materialSourceSystem: material?.sourceSystem ?? "ERPNEXT",
    materialSourceObjectId: material?.sourceObjectId ?? "",
    materialLabel: material?.label ?? "",
    materialQuantity:
      material?.quantity === null || material?.quantity === undefined
        ? ""
        : String(material.quantity),
    materialUnit: material?.unit ?? "",
    responsibleMemberGlobalIds:
      revision?.responsibleMembers
        .map((member) => member.globalId)
        .join(", ") ?? "",
    sampleQuantity: String(revision?.sampleQuantity ?? 1),
    measurementPlanDescription: revision?.measurementPlan.description ?? "",
    displayLabel: "",
    actionKey: "",
    actionTitle: "",
    actionDescription: "",
    actionResponsibleMemberGlobalId:
      revision?.responsibleMembers[0]?.globalId ?? "",
    actionDueAt: revision
      ? utcInput(revision.plannedEndAt)
      : utcInput(end.toISOString()),
    actionSeverity: "medium",
    actionBlocking: false,
    trialRoundGlobalId: detail?.rounds[0]?.globalId ?? "",
  };
}

function LoadingSurface(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section
      aria-busy="true"
      aria-label={t("Loading Trial planning workspace")}
      className="workspace-resource-state workspace-resource-state--loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">
        {t("Loading Trial planning workspace")}
      </span>
    </section>
  );
}

export default function LiveTrialPage({
  dataSource,
  navigate,
  projectId,
  reportWorkspaceDirty,
}: {
  dataSource: TrialDataSource;
  navigate: (target: string) => void;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [detailAttempt, setDetailAttempt] = useState(0);
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DetailState>({ kind: "idle" });
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const returnFocus = useRef<HTMLElement | null>(null);
  const firstEditorControl = useRef<HTMLInputElement | null>(null);
  const latestCommand = useRef<(() => void) | null>(null);
  const workspace = resource.kind === "loaded" ? resource.value : null;
  const planDetail = detail.kind === "loaded" ? detail.value : null;

  useEffect(() => {
    const controller = new AbortController();
    void dataSource
      .loadWorkspace(projectId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setResource({ kind: "loaded", value });
        const nextPlanId = value.plans[0]?.planGlobalId ?? null;
        setSelectedPlanId(nextPlanId);
        setDetail(nextPlanId ? { kind: "loading" } : { kind: "idle" });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof TrialRequestCancelledError
        )
          return;
        setResource({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, projectId]);

  useEffect(() => {
    if (!selectedPlanId) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadPlan(projectId, selectedPlanId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setDetail({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof TrialRequestCancelledError
        )
          return;
        setDetail({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, detailAttempt, projectId, selectedPlanId]);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!editor) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: selectedPlanId ?? `${projectId}:new-trial-plan`,
      version: planDetail
        ? `trial-plan-v${String(planDetail.latestRevision.planVersion)}`
        : "unsaved-trial-plan",
      returnFocusTarget: () =>
        firstEditorControl.current ??
        document.getElementById("trial-create-plan"),
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [editor, planDetail, projectId, reportWorkspaceDirty, selectedPlanId]);

  const closeEditor = useCallback((): void => {
    setEditor(null);
    setFormError(null);
    setReviewOpen(false);
    const target = returnFocus.current;
    globalThis.queueMicrotask(() => target?.focus());
  }, []);

  const openEditor = useCallback(
    (kind: EditorKind, trigger: HTMLElement): void => {
      returnFocus.current = trigger;
      setEditor(newEditor(kind, planDetail));
      setFormError(null);
      setCommand({ kind: "idle" });
      globalThis.queueMicrotask(() => firstEditorControl.current?.focus());
    },
    [planDetail],
  );

  const acceptCommand = useCallback(
    (result: TrialCommandResult, label: string): void => {
      const nextDetail = result.detail;
      setDetail({ kind: "loaded", value: nextDetail });
      setSelectedPlanId(nextDetail.planGlobalId);
      setResource((current) => {
        if (current.kind !== "loaded") return current;
        const nextSummary = {
          actionCount: nextDetail.actionLinks.length,
          latestRevision: nextDetail.latestRevision,
          planGlobalId: nextDetail.planGlobalId,
          roundCount: nextDetail.rounds.length,
        };
        const present = current.value.plans.some(
          (plan) => plan.planGlobalId === nextDetail.planGlobalId,
        );
        return {
          kind: "loaded",
          value: {
            ...current.value,
            plans: present
              ? current.value.plans.map((plan) =>
                  plan.planGlobalId === nextDetail.planGlobalId
                    ? nextSummary
                    : plan,
                )
              : [...current.value.plans, nextSummary],
          },
        };
      });
      setEditor(null);
      setReviewOpen(false);
      setFormError(null);
      setCommand({ kind: "succeeded", label, replayed: result.replayed });
      const target = returnFocus.current;
      globalThis.queueMicrotask(() => target?.focus());
    },
    [],
  );

  const runCommand = useCallback(
    (
      label: string,
      operation: (signal: AbortSignal) => Promise<TrialCommandResult>,
    ): void => {
      const execute = (): void => {
        const controller = new AbortController();
        setCommand({ kind: "processing", label });
        void operation(controller.signal)
          .then((result) => {
            acceptCommand(result, label);
          })
          .catch((error: unknown) => {
            if (
              controller.signal.aborted ||
              error instanceof TrialRequestCancelledError
            )
              return;
            setReviewOpen(false);
            setCommand({ kind: "failed", failure: toRequestFailure(error) });
          });
      };
      latestCommand.current = execute;
      execute();
    },
    [acceptCommand],
  );

  const planResources = useCallback(
    (value: EditorState): readonly TrialResourceProposalInput[] => {
      const materialQuantity = Number(value.materialQuantity);
      return [
        {
          kind: "machine",
          label: value.machineLabel.trim(),
          quantity: null,
          sourceObjectId: value.machineSourceObjectId.trim(),
          sourceSystem: value.machineSourceSystem,
          unit: null,
        },
        {
          kind: "material",
          label: value.materialLabel.trim(),
          quantity:
            value.materialQuantity.trim() && Number.isInteger(materialQuantity)
              ? materialQuantity
              : null,
          sourceObjectId: value.materialSourceObjectId.trim(),
          sourceSystem: value.materialSourceSystem,
          unit: value.materialUnit.trim() || null,
        },
      ];
    },
    [],
  );

  const editorIsValid = useMemo(() => {
    if (!editor) return false;
    if (editor.kind === "create_round") {
      return (
        !editor.displayLabel.trim() ||
        /^T(?:0|[1-9][0-9]{0,3})$/u.test(editor.displayLabel.trim())
      );
    }
    if (editor.kind === "generate_action") {
      return (
        /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/u.test(editor.actionKey.trim()) &&
        Boolean(editor.actionTitle.trim()) &&
        uuidPattern.test(editor.actionResponsibleMemberGlobalId.trim()) &&
        Boolean(editor.actionDueAt)
      );
    }
    const responsible = memberIds(editor.responsibleMemberGlobalIds);
    const quantity = Number(editor.sampleQuantity);
    const materialQuantity = editor.materialQuantity.trim()
      ? Number(editor.materialQuantity)
      : null;
    return (
      (editor.kind === "revise_plan" ||
        uuidPattern.test(editor.toolingMasterGlobalId.trim())) &&
      Boolean(editor.objective.trim()) &&
      Boolean(editor.plannedStartAt) &&
      Boolean(editor.plannedEndAt) &&
      Date.parse(`${editor.plannedStartAt}:00Z`) <
        Date.parse(`${editor.plannedEndAt}:00Z`) &&
      Boolean(editor.machineSourceObjectId.trim()) &&
      Boolean(editor.machineLabel.trim()) &&
      Boolean(editor.materialSourceObjectId.trim()) &&
      Boolean(editor.materialLabel.trim()) &&
      ((materialQuantity === null && !editor.materialUnit.trim()) ||
        (Number.isInteger(materialQuantity) &&
          Number(materialQuantity) > 0 &&
          Boolean(editor.materialUnit.trim()))) &&
      responsible.length >= 1 &&
      responsible.every((memberId) => uuidPattern.test(memberId)) &&
      new Set(responsible).size === responsible.length &&
      Number.isInteger(quantity) &&
      quantity > 0 &&
      Boolean(editor.measurementPlanDescription.trim())
    );
  }, [editor]);

  const reviewEditor = (): void => {
    if (!editorIsValid) {
      setFormError(
        t(
          "Complete every required Trial field with exact stable references before review.",
        ),
      );
      return;
    }
    setFormError(null);
    setReviewOpen(true);
  };

  const confirmEditor = (reason: string): void => {
    if (!editor || !sessionCommandContext || !workspace) return;
    const bindContext = (prefix: string) => {
      const idempotencyKey = `${prefix}-${globalThis.crypto.randomUUID()}`;
      return (signal: AbortSignal) => ({
        csrfToken: sessionCommandContext.csrfToken,
        idempotencyKey,
        signal,
      });
    };
    const label = commandProcessingLabel(t, editor.kind);
    if (editor.kind === "create_plan") {
      const commandValue: CreateTrialPlanCommand = {
        measurementPlan: {
          description: editor.measurementPlanDescription.trim(),
        },
        objective: editor.objective.trim(),
        plannedEndAt: utcInstant(editor.plannedEndAt),
        plannedStartAt: utcInstant(editor.plannedStartAt),
        purpose: editor.purpose,
        reason,
        resources: planResources(editor),
        responsibleMemberGlobalIds: memberIds(
          editor.responsibleMemberGlobalIds,
        ),
        sampleQuantity: Number(editor.sampleQuantity),
        toolingMasterGlobalId: editor.toolingMasterGlobalId.trim(),
      };
      const context = bindContext("trial-plan-create");
      runCommand(label, (signal) =>
        dataSource.createPlan(projectId, commandValue, context(signal)),
      );
      return;
    }
    if (!planDetail) return;
    const revision = planDetail.latestRevision;
    if (editor.kind === "revise_plan") {
      const commandValue: CreateTrialPlanRevisionCommand = {
        expectedPlanVersion: revision.planVersion,
        expectedRevisionGlobalId: revision.globalId,
        expectedRevisionSnapshotHash: revision.snapshotHash,
        measurementPlan: {
          description: editor.measurementPlanDescription.trim(),
        },
        objective: editor.objective.trim(),
        plannedEndAt: utcInstant(editor.plannedEndAt),
        plannedStartAt: utcInstant(editor.plannedStartAt),
        purpose: editor.purpose,
        reason,
        resources: planResources(editor),
        responsibleMemberGlobalIds: memberIds(
          editor.responsibleMemberGlobalIds,
        ),
        sampleQuantity: Number(editor.sampleQuantity),
      };
      const context = bindContext("trial-plan-revise");
      runCommand(label, (signal) =>
        dataSource.revisePlan(
          projectId,
          planDetail.planGlobalId,
          commandValue,
          context(signal),
        ),
      );
      return;
    }
    if (editor.kind === "create_round") {
      const commandValue: CreatePlannedTrialRoundCommand = {
        expectedPlanRevisionGlobalId: revision.globalId,
        expectedPlanRevisionSnapshotHash: revision.snapshotHash,
        ...(editor.displayLabel.trim()
          ? { displayLabel: editor.displayLabel.trim() }
          : {}),
        reason,
      };
      const context = bindContext("trial-round-create");
      runCommand(label, (signal) =>
        dataSource.createRound(
          projectId,
          planDetail.planGlobalId,
          commandValue,
          context(signal),
        ),
      );
      return;
    }
    const commandValue: GenerateTrialPlanActionsCommand = {
      actions: [
        {
          actionKey: editor.actionKey.trim(),
          blocking: editor.actionBlocking,
          description: editor.actionDescription.trim() || null,
          dueAt: utcInstant(editor.actionDueAt),
          responsibleMemberGlobalId:
            editor.actionResponsibleMemberGlobalId.trim(),
          severity: editor.actionSeverity,
          title: editor.actionTitle.trim(),
        },
      ],
      expectedPlanRevisionGlobalId: revision.globalId,
      expectedPlanRevisionSnapshotHash: revision.snapshotHash,
      reason,
      ...(editor.trialRoundGlobalId
        ? { trialRoundGlobalId: editor.trialRoundGlobalId }
        : {}),
    };
    const context = bindContext("trial-actions-generate");
    runCommand(label, (signal) =>
      dataSource.generateActions(
        projectId,
        planDetail.planGlobalId,
        commandValue,
        context(signal),
      ),
    );
  };

  if (resource.kind === "loading") return <LoadingSurface />;
  if (resource.kind === "failed") {
    return (
      <article className="page page--object">
        <Panel title={t("Trial planning workspace unavailable")}>
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
  if (!workspace) return <LoadingSurface />;

  const processing = command.kind === "processing";
  const canCreatePlan =
    workspace.permissions.canCreatePlan && sessionCommandContext !== null;
  const selectedSummary = workspace.plans.find(
    (plan) => plan.planGlobalId === selectedPlanId,
  );

  return (
    <article className="page page--object trial-live">
      <ObjectHeader
        code={projectId}
        metadata={
          <span>
            {t("Trial Plans")}:{" "}
            {formatNumber(locale, workspace.plans.length, 0)} ·{" "}
            {t("Planned Rounds")}:{" "}
            {formatNumber(
              locale,
              workspace.plans.reduce(
                (total, plan) => total + plan.roundCount,
                0,
              ),
              0,
            )}{" "}
            · {t("Generated actions")}:{" "}
            {formatNumber(
              locale,
              workspace.plans.reduce(
                (total, plan) => total + plan.actionCount,
                0,
              ),
              0,
            )}
          </span>
        }
        name={t("Trial planning workspace")}
        nameIsBusinessData={false}
        primaryAction={
          workspace.permissions.canCreatePlan
            ? {
                disabled: !canCreatePlan || processing,
                id: "trial-create-plan",
                label: t("Create Trial Plan"),
                onClick: () => {
                  const trigger = document.getElementById("trial-create-plan");
                  if (trigger) openEditor("create_plan", trigger);
                },
              }
            : undefined
        }
        secondaryAction={
          <Button
            onClick={() => {
              navigate(`/projects/${projectId}`);
            }}
          >
            {t("Return to project")}
          </Button>
        }
        source={source}
        status={
          <SemanticStatus label={t("Planning foundation active")} tone="info" />
        }
      />
      <SectionAnchors
        sections={[
          { id: "trial-live-plans", label: t("Trial Plans") },
          { id: "trial-live-rounds", label: t("Planned Rounds") },
          { id: "trial-live-actions", label: t("Generated actions") },
          { id: "trial-live-later", label: t("Later Trial sections") },
          { id: "trial-live-inspector", label: t("Trial truth inspector") },
        ]}
      />
      {!sessionCommandContext &&
      Object.values(workspace.permissions).some(Boolean) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Trial planning is read only in this session.")}</span>
          <span>
            {t(
              "Session verification is required before a Trial command can be submitted.",
            )}
          </span>
        </div>
      ) : null}
      {Object.values(workspace.permissions).every((allowed) => !allowed) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Trial planning is read only for this Project.")}</span>
          <span>
            {t(
              "The server, not the browser, controls each available Trial action.",
            )}
          </span>
        </div>
      ) : null}
      {command.kind === "processing" ? (
        <div
          className="scenario-banner scenario-banner--processing"
          role="status"
        >
          <span>{command.label}</span>
          <span>
            {t("The Trial command is being verified and committed atomically.")}
          </span>
        </div>
      ) : null}
      {command.kind === "succeeded" ? (
        <div className="scenario-banner scenario-banner--queued" role="status">
          <span>{command.label}</span>
          <span>
            {command.replayed
              ? t("The exact prior Trial command response was replayed safely.")
              : t(
                  "The Trial command was committed with immutable history and audit truth.",
                )}
          </span>
        </div>
      ) : null}
      {command.kind === "failed" ? (
        <Panel title={t("Trial command not completed")}>
          <RequestFailurePanel failure={command.failure} />
          {canRetry(command.failure) ? (
            <Button onClick={() => latestCommand.current?.()}>
              {t("Retry exact command")}
            </Button>
          ) : null}
        </Panel>
      ) : null}
      {workspace.plans.length === 0 ? (
        <div className="empty-state" role="status">
          <strong>
            {t("No Trial Plan has been recorded for this Project.")}
          </strong>
          <span>
            {t(
              "Create a Plan only when exact Tooling, responsible-member and proposed-resource references are known.",
            )}
          </span>
        </div>
      ) : null}
      {editor ? (
        <Panel title={editorLabel(t, editor.kind)}>
          <form
            className="trial-live__editor"
            onSubmit={(event) => {
              event.preventDefault();
              reviewEditor();
            }}
          >
            {editor.kind === "create_plan" || editor.kind === "revise_plan" ? (
              <>
                {editor.kind === "create_plan" ? (
                  <label>
                    <span>{t("Tooling Master stable ID")}</span>
                    <TextInput
                      aria-label={t("Tooling Master stable ID")}
                      disabled={processing}
                      onChange={(event) => {
                        setEditor({
                          ...editor,
                          toolingMasterGlobalId: event.target.value,
                        });
                      }}
                      ref={firstEditorControl}
                      value={editor.toolingMasterGlobalId}
                    />
                  </label>
                ) : null}
                <label>
                  <span>{t("Trial purpose")}</span>
                  <Select
                    aria-label={t("Trial purpose")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        purpose: event.target.value as TrialPurpose,
                      });
                    }}
                    value={editor.purpose}
                  >
                    {trialPurposes.map((purpose) => (
                      <option key={purpose} value={purpose}>
                        {purposeLabel(t, purpose)}
                      </option>
                    ))}
                  </Select>
                </label>
                <label className="trial-live__editor-wide">
                  <span>{t("Trial objective")}</span>
                  <textarea
                    aria-label={t("Trial objective")}
                    disabled={processing}
                    maxLength={2000}
                    onChange={(event) => {
                      setEditor({ ...editor, objective: event.target.value });
                    }}
                    rows={3}
                    value={editor.objective}
                  />
                </label>
                <label>
                  <span>{t("Planned start (UTC)")}</span>
                  <TextInput
                    aria-label={t("Planned start (UTC)")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        plannedStartAt: event.target.value,
                      });
                    }}
                    type="datetime-local"
                    value={editor.plannedStartAt}
                  />
                </label>
                <label>
                  <span>{t("Planned end (UTC)")}</span>
                  <TextInput
                    aria-label={t("Planned end (UTC)")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        plannedEndAt: event.target.value,
                      });
                    }}
                    type="datetime-local"
                    value={editor.plannedEndAt}
                  />
                </label>
                <fieldset className="trial-live__resource-editor">
                  <legend>{t("Proposed machine")}</legend>
                  <Select
                    aria-label={t("Machine source system")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        machineSourceSystem: event.target.value as
                          | "NPI_ONE"
                          | "ERPNEXT",
                      });
                    }}
                    value={editor.machineSourceSystem}
                  >
                    <option value="NPI_ONE">{t("NPI One")}</option>
                    <option value="ERPNEXT">{t("ERPNext")}</option>
                  </Select>
                  <TextInput
                    aria-label={t("Machine source object ID")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        machineSourceObjectId: event.target.value,
                      });
                    }}
                    placeholder={t("Machine source object ID")}
                    value={editor.machineSourceObjectId}
                  />
                  <TextInput
                    aria-label={t("Machine label")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        machineLabel: event.target.value,
                      });
                    }}
                    placeholder={t("Machine label")}
                    value={editor.machineLabel}
                  />
                </fieldset>
                <fieldset className="trial-live__resource-editor">
                  <legend>{t("Proposed material")}</legend>
                  <Select
                    aria-label={t("Material source system")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        materialSourceSystem: event.target.value as
                          | "NPI_ONE"
                          | "ERPNEXT",
                      });
                    }}
                    value={editor.materialSourceSystem}
                  >
                    <option value="NPI_ONE">{t("NPI One")}</option>
                    <option value="ERPNEXT">{t("ERPNext")}</option>
                  </Select>
                  <TextInput
                    aria-label={t("Material source object ID")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        materialSourceObjectId: event.target.value,
                      });
                    }}
                    placeholder={t("Material source object ID")}
                    value={editor.materialSourceObjectId}
                  />
                  <TextInput
                    aria-label={t("Material label")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        materialLabel: event.target.value,
                      });
                    }}
                    placeholder={t("Material label")}
                    value={editor.materialLabel}
                  />
                  <TextInput
                    aria-label={t("Material quantity")}
                    disabled={processing}
                    min="1"
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        materialQuantity: event.target.value,
                      });
                    }}
                    placeholder={t("Quantity")}
                    type="number"
                    value={editor.materialQuantity}
                  />
                  <TextInput
                    aria-label={t("Material unit")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        materialUnit: event.target.value,
                      });
                    }}
                    placeholder={t("Unit")}
                    value={editor.materialUnit}
                  />
                </fieldset>
                <label className="trial-live__editor-wide">
                  <span>{t("Responsible Project member stable IDs")}</span>
                  <TextInput
                    aria-label={t("Responsible Project member stable IDs")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        responsibleMemberGlobalIds: event.target.value,
                      });
                    }}
                    placeholder={t("Separate multiple stable IDs with commas")}
                    value={editor.responsibleMemberGlobalIds}
                  />
                </label>
                <label>
                  <span>{t("Planned sample quantity")}</span>
                  <TextInput
                    aria-label={t("Planned sample quantity")}
                    disabled={processing}
                    min="1"
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        sampleQuantity: event.target.value,
                      });
                    }}
                    type="number"
                    value={editor.sampleQuantity}
                  />
                </label>
                <label className="trial-live__editor-wide">
                  <span>{t("Measurement-plan intent")}</span>
                  <textarea
                    aria-label={t("Measurement-plan intent")}
                    disabled={processing}
                    maxLength={1000}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        measurementPlanDescription: event.target.value,
                      });
                    }}
                    rows={3}
                    value={editor.measurementPlanDescription}
                  />
                </label>
              </>
            ) : editor.kind === "create_round" ? (
              <label>
                <span>{t("Optional Round label")}</span>
                <TextInput
                  aria-label={t("Optional Round label")}
                  disabled={processing}
                  onChange={(event) => {
                    setEditor({ ...editor, displayLabel: event.target.value });
                  }}
                  placeholder={t("Leave blank for the next server label")}
                  ref={firstEditorControl}
                  value={editor.displayLabel}
                />
              </label>
            ) : (
              <>
                <label>
                  <span>{t("Action key")}</span>
                  <TextInput
                    aria-label={t("Action key")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({ ...editor, actionKey: event.target.value });
                    }}
                    ref={firstEditorControl}
                    value={editor.actionKey}
                  />
                </label>
                <label className="trial-live__editor-wide">
                  <span>{t("Action title")}</span>
                  <TextInput
                    aria-label={t("Action title")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({ ...editor, actionTitle: event.target.value });
                    }}
                    value={editor.actionTitle}
                  />
                </label>
                <label className="trial-live__editor-wide">
                  <span>{t("Action description")}</span>
                  <textarea
                    aria-label={t("Action description")}
                    disabled={processing}
                    maxLength={2000}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        actionDescription: event.target.value,
                      });
                    }}
                    rows={3}
                    value={editor.actionDescription}
                  />
                </label>
                <label>
                  <span>{t("Responsible Project member stable ID")}</span>
                  <TextInput
                    aria-label={t("Responsible Project member stable ID")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        actionResponsibleMemberGlobalId: event.target.value,
                      });
                    }}
                    value={editor.actionResponsibleMemberGlobalId}
                  />
                </label>
                <label>
                  <span>{t("Action due time (UTC)")}</span>
                  <TextInput
                    aria-label={t("Action due time (UTC)")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({ ...editor, actionDueAt: event.target.value });
                    }}
                    type="datetime-local"
                    value={editor.actionDueAt}
                  />
                </label>
                <label>
                  <span>{t("Action severity")}</span>
                  <Select
                    aria-label={t("Action severity")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        actionSeverity: event.target
                          .value as TrialActionSeverity,
                      });
                    }}
                    value={editor.actionSeverity}
                  >
                    {trialActionSeverities.map((severity) => (
                      <option key={severity} value={severity}>
                        {severityLabel(t, severity)}
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("Related Trial Round")}</span>
                  <Select
                    aria-label={t("Related Trial Round")}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        trialRoundGlobalId: event.target.value,
                      });
                    }}
                    value={editor.trialRoundGlobalId}
                  >
                    <option value="">{t("Plan only")}</option>
                    {planDetail?.rounds.map((round) => (
                      <option key={round.globalId} value={round.globalId}>
                        {round.displayLabel}
                      </option>
                    ))}
                  </Select>
                </label>
                <label className="trial-live__checkbox">
                  <input
                    checked={editor.actionBlocking}
                    disabled={processing}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        actionBlocking: event.target.checked,
                      });
                    }}
                    type="checkbox"
                  />
                  <span>{t("Blocking action")}</span>
                </label>
              </>
            )}
            <p className="context-help trial-live__editor-wide">
              {editor.kind === "create_round"
                ? t(
                    "The Round will be created only in planned state against the exact current Plan revision.",
                  )
                : editor.kind === "generate_action"
                  ? t(
                      "The generated record uses the governed Project Work lifecycle; Trial stores only an immutable link.",
                    )
                  : t(
                      "Resource entries are proposals only. Availability and reservation remain unavailable.",
                    )}
            </p>
            {formError ? (
              <p className="form-error trial-live__editor-wide" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions trial-live__editor-wide">
              <Button disabled={processing} type="submit" visual="primary">
                {t("Review command")}
              </Button>
              <Button disabled={processing} onClick={closeEditor}>
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}
      <div className="trial-live__layout">
        <Panel title={t("Trial Plans")}>
          <ul className="object-tree" id="trial-live-plans" tabIndex={-1}>
            {workspace.plans.map((plan) => (
              <li key={plan.planGlobalId}>
                <button
                  aria-current={selectedPlanId === plan.planGlobalId}
                  className="trial-live__tree-control"
                  onClick={() => {
                    setDetail({ kind: "loading" });
                    setSelectedPlanId(plan.planGlobalId);
                    setCommand({ kind: "idle" });
                  }}
                  type="button"
                >
                  <strong data-language-exempt="business-data">
                    {plan.latestRevision.objective}
                  </strong>
                  <span className="trial-live__tree-meta">
                    {t("Version {{version}}", {
                      version: plan.latestRevision.planVersion,
                    })}{" "}
                    · {purposeLabel(t, plan.latestRevision.purpose)}
                  </span>
                  <small className="trial-live__tree-meta">
                    {t("{{rounds}} Rounds, {{actions}} actions", {
                      actions: formatNumber(locale, plan.actionCount, 0),
                      rounds: formatNumber(locale, plan.roundCount, 0),
                    })}
                  </small>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
        <div className="trial-live__center">
          {detail.kind === "loading" ? <LoadingSurface /> : null}
          {detail.kind === "failed" ? (
            <Panel title={t("Trial Plan unavailable")}>
              <RequestFailurePanel failure={detail.failure} />
              {canRetry(detail.failure) ? (
                <Button
                  onClick={() => {
                    setDetail({ kind: "loading" });
                    setDetailAttempt((current) => current + 1);
                  }}
                >
                  {t("Retry")}
                </Button>
              ) : null}
            </Panel>
          ) : null}
          {planDetail ? (
            <>
              <Panel title={t("Current Trial Plan revision")}>
                <div className="trial-live__command-bar">
                  {workspace.permissions.canRevisePlan ? (
                    <Button
                      disabled={!sessionCommandContext || processing}
                      onClick={(event) => {
                        openEditor("revise_plan", event.currentTarget);
                      }}
                    >
                      {t("Append revision")}
                    </Button>
                  ) : null}
                  {workspace.permissions.canCreateRound ? (
                    <Button
                      disabled={!sessionCommandContext || processing}
                      onClick={(event) => {
                        openEditor("create_round", event.currentTarget);
                      }}
                    >
                      {t("Create planned Round")}
                    </Button>
                  ) : null}
                  {workspace.permissions.canGenerateActions ? (
                    <Button
                      disabled={!sessionCommandContext || processing}
                      onClick={(event) => {
                        openEditor("generate_action", event.currentTarget);
                      }}
                    >
                      {t("Generate action")}
                    </Button>
                  ) : null}
                </div>
                <DefinitionList
                  rows={[
                    {
                      label: t("Objective"),
                      value: planDetail.latestRevision.objective,
                      exempt: "business-data",
                    },
                    {
                      label: t("Purpose"),
                      value: purposeLabel(t, planDetail.latestRevision.purpose),
                    },
                    {
                      label: t("Plan version"),
                      value: formatNumber(
                        locale,
                        planDetail.latestRevision.planVersion,
                        0,
                      ),
                    },
                    {
                      label: t("Tooling Master stable ID"),
                      value: planDetail.latestRevision.toolingMasterGlobalId,
                      exempt: "identifier",
                    },
                    {
                      label: t("Planned start"),
                      value: formatDateTime(
                        locale,
                        planDetail.latestRevision.plannedStartAt,
                      ),
                    },
                    {
                      label: t("Planned end"),
                      value: formatDateTime(
                        locale,
                        planDetail.latestRevision.plannedEndAt,
                      ),
                    },
                    {
                      label: t("Planned sample quantity"),
                      value: formatNumber(
                        locale,
                        planDetail.latestRevision.sampleQuantity,
                        0,
                      ),
                    },
                    {
                      label: t("Measurement-plan intent"),
                      value:
                        planDetail.latestRevision.measurementPlan.description ??
                        t("Controlled document intent only"),
                      exempt: "business-data",
                    },
                  ]}
                />
              </Panel>
              <Panel title={t("Proposed resources")}>
                <table
                  aria-label={t("Proposed resources")}
                  className="data-table"
                  tabIndex={0}
                >
                  <thead>
                    <tr>
                      <th>{t("Resource kind")}</th>
                      <th>{t("Resource")}</th>
                      <th>{t("Source")}</th>
                      <th>{t("Quantity")}</th>
                      <th>{t("Booking state")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {planDetail.latestRevision.resources.map((item) => (
                      <tr key={item.globalId}>
                        <td>
                          {item.kind === "machine"
                            ? t("Machine")
                            : item.kind === "material"
                              ? t("Material")
                              : t("Auxiliary equipment")}
                        </td>
                        <td>
                          <span data-language-exempt="business-data">
                            {item.label}
                          </span>
                          <small
                            className="trial-live__resource-reference"
                            data-language-exempt="identifier"
                          >
                            {item.sourceObjectId}
                          </small>
                        </td>
                        <td data-language-exempt="identifier">
                          {item.sourceSystem}
                        </td>
                        <td>
                          {item.quantity === null
                            ? t("Not specified")
                            : `${formatNumber(locale, item.quantity, 0)} ${item.unit ?? ""}`}
                        </td>
                        <td>
                          <SemanticStatus
                            label={t("Unavailable")}
                            tone="warning"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
              <Panel title={t("Responsible Project members")}>
                <table
                  aria-label={t("Responsible Project members")}
                  className="data-table"
                  tabIndex={0}
                >
                  <thead>
                    <tr>
                      <th>{t("Member")}</th>
                      <th>{t("User")}</th>
                      <th>{t("Member version")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {planDetail.latestRevision.responsibleMembers.map(
                      (member) => (
                        <tr key={member.globalId}>
                          <td data-language-exempt="identifier">
                            {member.globalId}
                          </td>
                          <td data-language-exempt="business-data">
                            {member.userId}
                          </td>
                          <td>
                            {formatNumber(locale, member.optimisticVersion, 0)}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </Panel>
              <Panel title={t("Immutable Plan revision history")}>
                <table
                  aria-label={t("Immutable Plan revision history")}
                  className="data-table"
                  tabIndex={0}
                >
                  <thead>
                    <tr>
                      <th>{t("Version")}</th>
                      <th>{t("Reason")}</th>
                      <th>{t("Created by")}</th>
                      <th>{t("Created at")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {planDetail.revisions.map((revision) => (
                      <tr key={revision.globalId}>
                        <td>{formatNumber(locale, revision.planVersion, 0)}</td>
                        <td data-language-exempt="business-data">
                          {revision.reason}
                        </td>
                        <td data-language-exempt="business-data">
                          {revision.createdByUserId}
                        </td>
                        <td>{formatDateTime(locale, revision.createdAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
              <Panel title={t("Planned Rounds")}>
                <div id="trial-live-rounds" tabIndex={-1} />
                {planDetail.rounds.length ? (
                  <table
                    aria-label={t("Planned Rounds")}
                    className="data-table"
                    tabIndex={0}
                  >
                    <thead>
                      <tr>
                        <th>{t("Round")}</th>
                        <th>{t("State")}</th>
                        <th>{t("Plan version")}</th>
                        <th>{t("Planned interval")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {planDetail.rounds.map((round) => (
                        <tr key={round.globalId}>
                          <td data-language-exempt="identifier">
                            {round.displayLabel}
                          </td>
                          <td>
                            <SemanticStatus
                              label={roundStateLabel(t, round.currentState)}
                              tone="info"
                            />
                          </td>
                          <td data-language-exempt="identifier">
                            {round.trialPlanRevisionGlobalId}
                          </td>
                          <td>
                            {formatDateTime(locale, round.plannedStartAt)} –{" "}
                            {formatDateTime(locale, round.plannedEndAt)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p>
                    {t(
                      "No planned Trial Round is linked to this Plan revision history.",
                    )}
                  </p>
                )}
              </Panel>
              <Panel title={t("Generated actions")}>
                <div id="trial-live-actions" tabIndex={-1} />
                {planDetail.actionLinks.length ? (
                  <table
                    aria-label={t("Generated actions")}
                    className="data-table"
                    tabIndex={0}
                  >
                    <thead>
                      <tr>
                        <th>{t("Domain Work Item")}</th>
                        <th>{t("Plan revision")}</th>
                        <th>{t("Related Round")}</th>
                        <th>{t("Linked at")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {planDetail.actionLinks.map((link) => (
                        <tr key={link.globalId}>
                          <td data-language-exempt="identifier">
                            {link.domainWorkItemGlobalId}
                          </td>
                          <td data-language-exempt="identifier">
                            {link.trialPlanRevisionGlobalId}
                          </td>
                          <td data-language-exempt="identifier">
                            {link.trialRoundGlobalId ?? "—"}
                          </td>
                          <td>{formatDateTime(locale, link.createdAt)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p>
                    {t(
                      "No governed Project Work action is linked to this Trial Plan.",
                    )}
                  </p>
                )}
              </Panel>
              <Panel title={t("Later Trial sections")}>
                <div
                  className="trial-live__later"
                  id="trial-live-later"
                  tabIndex={-1}
                >
                  {[
                    t("Locked preparation inputs"),
                    t("Actual process parameters"),
                    t("Samples and cavity evidence"),
                    t("Defects and measurements"),
                    t("Conclusion and approval"),
                    t("Formal quality and ERPNext execution"),
                  ].map((label) => (
                    <div className="trial-live__later-item" key={label}>
                      <SemanticStatus
                        label={t("Unavailable in this checkpoint")}
                        tone="neutral"
                      />
                      <span>{label}</span>
                    </div>
                  ))}
                </div>
              </Panel>
            </>
          ) : selectedSummary && detail.kind === "idle" ? (
            <LoadingSurface />
          ) : null}
        </div>
        <DockedInspector
          id="trial-live-inspector"
          title={t("Trial truth inspector")}
        >
          <DefinitionList
            rows={[
              {
                label: t("Project stable ID"),
                value: projectId,
                exempt: "identifier",
              },
              {
                label: t("Plan stable ID"),
                value: planDetail?.planGlobalId ?? t("No Plan selected"),
                ...(planDetail ? { exempt: "identifier" as const } : {}),
              },
              {
                label: t("Plan snapshot"),
                value:
                  planDetail?.latestRevision.snapshotHash ?? t("Unavailable"),
                ...(planDetail ? { exempt: "identifier" as const } : {}),
              },
              { label: t("Resource availability"), value: t("Unavailable") },
              { label: t("Resource reservation"), value: t("Unavailable") },
              { label: t("Action state owner"), value: t("Project Work") },
              {
                label: t("Formal resource and quality owner"),
                value: "ERPNext",
                exempt: "identifier",
              },
            ]}
          />
          <div className="blocking-message failure-explanation">
            <SemanticStatus label={t("No booking claim")} tone="warning" />
            <p>
              {t(
                "An approved resource reader and booking policy are not configured. Proposed resources are not confirmed or reserved.",
              )}
            </p>
          </div>
          <div className="blocking-message">
            <SemanticStatus label={t("Planned state only")} tone="neutral" />
            <p>
              {t(
                "P7-01 creates only planned Rounds. Preparation, execution, evidence, conclusion and approval remain unavailable.",
              )}
            </p>
          </div>
        </DockedInspector>
      </div>
      {reviewOpen && editor ? (
        <ImpactReview
          confirmLabel={editorLabel(t, editor.kind)}
          details={{
            objectIdentity: planDetail?.planGlobalId ?? projectId,
            version: planDetail
              ? `v${String(planDetail.latestRevision.planVersion)}`
              : t("Initial revision"),
            impact:
              editor.kind === "generate_action"
                ? t(
                    "Creates one governed Domain Work Item and an immutable Trial link.",
                  )
                : t(
                    "Appends immutable Trial planning history; prior versions are not overwritten.",
                  ),
            permission: t(
              "The server rechecks Project membership and System Manager command authority.",
            ),
            irreversible: t(
              "Committed Trial history cannot be edited or deleted through generic CRUD.",
            ),
            failureHandling: t(
              "A failed command changes no Trial or Project Work row and can be retried with the same exact request.",
            ),
            audit: t(
              "The command records actor, request, trace, reason and immutable snapshot evidence.",
            ),
          }}
          onCancel={() => {
            setReviewOpen(false);
          }}
          onConfirm={confirmEditor}
          reasonMaxLength={500}
          returnFocusTarget={() => returnFocus.current}
          title={t("Review immutable Trial command")}
        />
      ) : null}
    </article>
  );
}
