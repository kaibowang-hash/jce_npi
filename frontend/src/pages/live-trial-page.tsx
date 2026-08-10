import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  trialEvidenceRoles,
  trialLockedReferenceKinds,
  trialParameterValueKinds,
  trialActionSeverities,
  trialPurposes,
  TrialRequestCancelledError,
  type AppendTrialActualRevisionCommand,
  type AppendTrialSampleBatchRevisionCommand,
  type BindTrialEvidenceCommand,
  type CreatePlannedTrialRoundCommand,
  type CreateTrialSampleBatchCommand,
  type CreateTrialPlanCommand,
  type CreateTrialPlanRevisionCommand,
  type GenerateTrialPlanActionsCommand,
  type PrepareTrialRoundCommand,
  type StartTrialRoundCommand,
  type TrialActionSeverity,
  type TrialCommandResult,
  type TrialDataSource,
  type TrialEvidenceReference,
  type TrialEvidenceRole,
  type TrialExecutionCommandResult,
  type TrialExecutionWorkspace,
  type TrialLockedReferenceKind,
  type TrialParameterValueKind,
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
type ExecutionState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; value: TrialExecutionWorkspace }
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

type ExecutionEditorKind =
  | "prepare"
  | "actual"
  | "create_sample"
  | "revise_sample"
  | "upload"
  | "bind_evidence";

interface PrepareEditorState {
  references: Record<
    TrialLockedReferenceKind,
    { globalId: string; optimisticVersion: string }
  >;
  materialSourceSystem: "NPI_ONE" | "ERPNEXT";
  materialSourceObjectId: string;
  materialLotBatchCode: string;
  materialLabel: string;
  materialColor: string;
  materialAdditive: string;
  materialObservedAt: string;
  definitions: {
    key: string;
    category: string;
    valueKind: TrialParameterValueKind;
    required: boolean;
    unit: string;
    targetValue: string;
    lowerLimit: string;
    upperLimit: string;
  }[];
}

interface ActualEditorState {
  resourceSourceSystem: "NPI_ONE" | "ERPNEXT";
  resourceSourceObjectId: string;
  resourceLabel: string;
  environmentKey: string;
  environmentValue: string;
  environmentUnit: string;
  operatorUserId: string;
  executionStartedAt: string;
  parameters: Record<
    string,
    { state: "measured" | "not_measured"; value: string }
  >;
}

interface SampleEditorState {
  revisionGlobalId: string | null;
  sampleBatchGlobalId: string | null;
  sampleVersion: number | null;
  label: string;
  cavityGlobalIds: string;
  quantity: string;
  unit: string;
  packaging: string;
  destination: string;
  feedbackText: string;
  feedbackSource: string;
  feedbackObservedAt: string;
}

function referenceKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: TrialLockedReferenceKind,
): string {
  switch (kind) {
    case "design_baseline":
      return t("Design baseline");
    case "part_revision":
      return t("Part revision");
    case "tooling_revision":
      return t("Tooling revision");
    case "tooling_set":
      return t("Tooling Set");
    case "tooling_set_binding":
      return t("Tooling Set binding");
    case "cavity":
      return t("Cavity");
    case "process_chain":
      return t("Process chain");
    case "inspection_document":
      return t("Inspection document");
  }
}

function evidenceRoleLabel(
  t: ReturnType<typeof useI18n>["t"],
  role: TrialEvidenceRole,
): string {
  switch (role) {
    case "photo":
      return t("Photo");
    case "video":
      return t("Video");
    case "parameter_curve":
      return t("Parameter curve");
    case "measurement_report":
      return t("Measurement report");
    case "customer_feedback":
      return t("Customer feedback");
  }
}

function missingFactLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: string,
): string {
  if (value === "input_lock") return t("Locked input revision");
  if (value === "actual_context") return t("Actual execution context");
  if (value === "sample_batch") return t("Sample Batch");
  if (value === "evidence") return t("Clean evidence");
  if (value.startsWith("parameter:")) {
    return t("Measured parameter: {{key}}", { key: value.slice(10) });
  }
  return value;
}

function initialPrepareEditor(
  workspace: TrialExecutionWorkspace,
  detail: TrialPlanDetail,
): PrepareEditorState {
  const material = detail.latestRevision.resources.find(
    (resource) => resource.kind === "material",
  );
  const references = Object.fromEntries(
    trialLockedReferenceKinds.map((kind) => [
      kind,
      { globalId: "", optimisticVersion: "1" },
    ]),
  ) as PrepareEditorState["references"];
  return {
    definitions: [
      {
        category: "",
        key: "",
        lowerLimit: "",
        required: true,
        targetValue: "",
        unit: "",
        upperLimit: "",
        valueKind: "decimal",
      },
    ],
    materialAdditive: "",
    materialColor: "",
    materialLabel: material?.label ?? "",
    materialLotBatchCode: "",
    materialObservedAt: utcInput(workspace.round.plannedStartAt),
    materialSourceObjectId: material?.sourceObjectId ?? "",
    materialSourceSystem: material?.sourceSystem ?? "ERPNEXT",
    references,
  };
}

function initialActualEditor(
  workspace: TrialExecutionWorkspace,
  detail: TrialPlanDetail,
  userId: string,
): ActualEditorState {
  const latest = workspace.actualRevisions.at(-1);
  const resource =
    latest?.resources[0] ??
    detail.latestRevision.resources.find(
      (candidate) => candidate.kind === "machine",
    );
  const definitions = workspace.inputLocks.at(-1)?.parameterDefinitions ?? [];
  const observed = new Map(
    latest?.parameters.map((parameter) => [parameter.definitionKey, parameter]),
  );
  return {
    environmentKey: latest?.environment[0]?.key ?? "",
    environmentUnit: latest?.environment[0]?.unit ?? "",
    environmentValue: latest?.environment[0]?.value ?? "",
    executionStartedAt: utcInput(
      latest?.executionStartedAt ?? workspace.round.plannedStartAt,
    ),
    operatorUserId: latest?.operatorUserId ?? userId,
    parameters: Object.fromEntries(
      definitions.map((definition) => {
        const value = observed.get(definition.key);
        return [
          definition.key,
          {
            state: value?.state ?? "not_measured",
            value: value?.value ?? "",
          },
        ];
      }),
    ),
    resourceLabel: resource?.label ?? "",
    resourceSourceObjectId: resource?.sourceObjectId ?? "",
    resourceSourceSystem: resource?.sourceSystem ?? "ERPNEXT",
  };
}

function initialSampleEditor(
  workspace: TrialExecutionWorkspace,
  revisionGlobalId?: string,
): SampleEditorState {
  const sample = revisionGlobalId
    ? workspace.sampleBatchRevisions.find(
        (candidate) => candidate.globalId === revisionGlobalId,
      )
    : null;
  const cavityIds = workspace.inputLocks
    .at(-1)
    ?.references.filter((reference) => reference.kind === "cavity")
    .map((reference) => reference.globalId);
  return {
    cavityGlobalIds:
      sample?.cavityGlobalIds.join(", ") ?? cavityIds?.join(", ") ?? "",
    destination: sample?.destination ?? "",
    feedbackObservedAt: sample?.feedbackObservedAt
      ? utcInput(sample.feedbackObservedAt)
      : "",
    feedbackSource: sample?.feedbackSource ?? "",
    feedbackText: sample?.feedbackText ?? "",
    label: sample?.label ?? "",
    packaging: sample?.packaging ?? "",
    quantity: sample ? String(sample.quantity) : "",
    revisionGlobalId: sample?.globalId ?? null,
    sampleBatchGlobalId: sample?.sampleBatchGlobalId ?? null,
    sampleVersion: sample?.sampleVersion ?? null,
    unit: sample?.unit ?? "pcs",
  };
}

function TrialExecutionSection({
  dataSource,
  detail,
  onWorkspace,
  projectId,
  reportWorkspaceDirty,
  workspace,
}: {
  dataSource: TrialDataSource;
  detail: TrialPlanDetail;
  onWorkspace: (value: TrialExecutionWorkspace) => void;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  workspace: TrialExecutionWorkspace;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [editorKind, setEditorKind] = useState<ExecutionEditorKind | null>(
    null,
  );
  const [prepareEditor, setPrepareEditor] = useState(() =>
    initialPrepareEditor(workspace, detail),
  );
  const [actualEditor, setActualEditor] = useState(() =>
    initialActualEditor(workspace, detail, sessionCommandContext?.userId ?? ""),
  );
  const [sampleEditor, setSampleEditor] = useState(() =>
    initialSampleEditor(workspace),
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [bindFileId, setBindFileId] = useState<string | null>(null);
  const [bindRole, setBindRole] = useState<TrialEvidenceRole>("photo");
  const [bindSampleRevisionId, setBindSampleRevisionId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const latestCommand = useRef<(() => void) | null>(null);
  const firstControl = useRef<HTMLInputElement | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const latestLock = workspace.inputLocks.at(-1) ?? null;
  const latestActual = workspace.actualRevisions.at(-1) ?? null;
  const processing = command.kind === "processing";

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!editorKind) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: workspace.round.globalId,
      returnFocusTarget: () =>
        firstControl.current ??
        document.getElementById("trial-execution-primary-action"),
      version: `trial-round-v${String(workspace.round.optimisticVersion)}`,
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [editorKind, reportWorkspaceDirty, workspace.round]);

  const closeEditor = (): void => {
    setEditorKind(null);
    setReviewOpen(false);
    setFormError(null);
    const target = returnFocus.current;
    globalThis.queueMicrotask(() => target?.focus());
  };

  const openEditor = (
    kind: ExecutionEditorKind,
    trigger: HTMLElement,
    revisionGlobalId?: string,
  ): void => {
    returnFocus.current = trigger;
    setCommand({ kind: "idle" });
    setFormError(null);
    setReviewOpen(false);
    setEditorKind(kind);
    if (kind === "prepare")
      setPrepareEditor(initialPrepareEditor(workspace, detail));
    if (kind === "actual")
      setActualEditor(
        initialActualEditor(
          workspace,
          detail,
          sessionCommandContext?.userId ?? "",
        ),
      );
    if (kind === "create_sample")
      setSampleEditor(initialSampleEditor(workspace));
    if (kind === "revise_sample")
      setSampleEditor(initialSampleEditor(workspace, revisionGlobalId));
    if (kind === "upload") setSelectedFile(null);
    if (kind !== "bind_evidence") setBindFileId(null);
    globalThis.queueMicrotask(() => firstControl.current?.focus());
  };

  const acceptExecution = (
    result: TrialExecutionCommandResult,
    label: string,
  ): void => {
    onWorkspace(result.workspace);
    setEditorKind(null);
    setReviewOpen(false);
    setFormError(null);
    setCommand({ kind: "succeeded", label, replayed: result.replayed });
    const target = returnFocus.current;
    globalThis.queueMicrotask(() => target?.focus());
  };

  const runExecutionCommand = (
    label: string,
    operation: () => Promise<TrialExecutionCommandResult>,
  ): void => {
    const execute = (): void => {
      setCommand({ kind: "processing", label });
      void operation()
        .then((result) => {
          acceptExecution(result, label);
        })
        .catch((error: unknown) => {
          setReviewOpen(false);
          setCommand({ kind: "failed", failure: toRequestFailure(error) });
        });
    };
    latestCommand.current = execute;
    execute();
  };

  const contextFor = (prefix: string) => {
    if (!sessionCommandContext) return null;
    const context = {
      csrfToken: sessionCommandContext.csrfToken,
      idempotencyKey: `${prefix}-${globalThis.crypto.randomUUID()}`,
      signal: new AbortController().signal,
    };
    return context;
  };

  const prepareValid =
    trialLockedReferenceKinds.every((kind) => {
      const reference = prepareEditor.references[kind];
      return (
        uuidPattern.test(reference.globalId.trim()) &&
        Number.isInteger(Number(reference.optimisticVersion)) &&
        Number(reference.optimisticVersion) > 0
      );
    }) &&
    Boolean(prepareEditor.materialSourceObjectId.trim()) &&
    Boolean(prepareEditor.materialLotBatchCode.trim()) &&
    Boolean(prepareEditor.materialLabel.trim()) &&
    Boolean(prepareEditor.materialObservedAt) &&
    prepareEditor.definitions.length >= 1 &&
    prepareEditor.definitions.every(
      (definition) =>
        Boolean(definition.key.trim()) &&
        Boolean(definition.category.trim()) &&
        (!(["decimal", "integer"] as const).includes(
          definition.valueKind as "decimal" | "integer",
        ) ||
          Boolean(definition.unit.trim())),
    );
  const actualValid =
    Boolean(latestLock) &&
    Boolean(actualEditor.resourceSourceObjectId.trim()) &&
    Boolean(actualEditor.resourceLabel.trim()) &&
    actualEditor.operatorUserId.includes("@") &&
    Boolean(actualEditor.executionStartedAt) &&
    (latestLock?.parameterDefinitions.every((definition) => {
      const observation = actualEditor.parameters[definition.key];
      return (
        observation !== undefined &&
        (observation.state === "not_measured" ||
          Boolean(observation.value.trim()))
      );
    }) ??
      false) &&
    ((!actualEditor.environmentKey.trim() &&
      !actualEditor.environmentValue.trim() &&
      !actualEditor.environmentUnit.trim()) ||
      (Boolean(actualEditor.environmentKey.trim()) &&
        Boolean(actualEditor.environmentValue.trim())));
  const cavityIds = memberIds(sampleEditor.cavityGlobalIds);
  const feedbackValues = [
    sampleEditor.feedbackText.trim(),
    sampleEditor.feedbackSource.trim(),
    sampleEditor.feedbackObservedAt,
  ];
  const sampleValid =
    Boolean(latestLock) &&
    Boolean(sampleEditor.label.trim()) &&
    cavityIds.length >= 1 &&
    cavityIds.every((value) => uuidPattern.test(value)) &&
    new Set(cavityIds).size === cavityIds.length &&
    Number.isInteger(Number(sampleEditor.quantity)) &&
    Number(sampleEditor.quantity) > 0 &&
    Boolean(sampleEditor.unit.trim()) &&
    Boolean(sampleEditor.packaging.trim()) &&
    Boolean(sampleEditor.destination.trim()) &&
    (feedbackValues.every((value) => !value) ||
      feedbackValues.every((value) => Boolean(value)));

  const reviewExecution = (): void => {
    const valid =
      editorKind === "prepare"
        ? prepareValid
        : editorKind === "actual"
          ? actualValid
          : editorKind === "create_sample" || editorKind === "revise_sample"
            ? sampleValid
            : false;
    if (!valid) {
      setFormError(
        t(
          "Complete every required execution field with exact references before review.",
        ),
      );
      return;
    }
    setFormError(null);
    setReviewOpen(true);
  };

  const confirmExecution = (reason: string): void => {
    if (!editorKind || !sessionCommandContext) return;
    const round = workspace.round;
    if (editorKind === "prepare") {
      const context = contextFor("trial-round-prepare");
      if (!context) return;
      const commandValue: PrepareTrialRoundCommand = {
        expectedRoundOptimisticVersion: round.optimisticVersion,
        material: {
          additive: prepareEditor.materialAdditive.trim() || null,
          color: prepareEditor.materialColor.trim() || null,
          label: prepareEditor.materialLabel.trim(),
          lotBatchCode: prepareEditor.materialLotBatchCode.trim(),
          observedAt: utcInstant(prepareEditor.materialObservedAt),
          sourceObjectId: prepareEditor.materialSourceObjectId.trim(),
          sourceSystem: prepareEditor.materialSourceSystem,
        },
        parameterDefinitions: prepareEditor.definitions.map((definition) => ({
          category: definition.category.trim(),
          key: definition.key.trim(),
          lowerLimit: definition.lowerLimit.trim() || null,
          required: definition.required,
          targetValue: definition.targetValue.trim() || null,
          unit: definition.unit.trim() || null,
          upperLimit: definition.upperLimit.trim() || null,
          valueKind: definition.valueKind,
        })),
        reason,
        references: trialLockedReferenceKinds.map((kind) => ({
          expectedOptimisticVersion: Number(
            prepareEditor.references[kind].optimisticVersion,
          ),
          globalId: prepareEditor.references[kind].globalId.trim(),
          kind,
        })),
      };
      runExecutionCommand(t("Preparing Trial Round"), () =>
        dataSource.prepareRound(
          projectId,
          round.globalId,
          commandValue,
          context,
        ),
      );
      return;
    }
    if (editorKind === "actual" && latestLock) {
      const context = contextFor(
        latestActual ? "trial-actual-revise" : "trial-round-start",
      );
      if (!context) return;
      const actualContext = {
        environment: actualEditor.environmentKey.trim()
          ? [
              {
                key: actualEditor.environmentKey.trim(),
                observedAt: utcInstant(actualEditor.executionStartedAt),
                unit: actualEditor.environmentUnit.trim() || null,
                value: actualEditor.environmentValue.trim(),
              },
            ]
          : [],
        executionStartedAt: utcInstant(actualEditor.executionStartedAt),
        material: {
          additive: latestLock.material.additive,
          color: latestLock.material.color,
          label: latestLock.material.label,
          lotBatchCode: latestLock.material.lotBatchCode,
          observedAt: latestLock.material.observedAt,
          sourceObjectId: latestLock.material.sourceObjectId,
          sourceSystem: latestLock.material.sourceSystem,
        },
        operatorUserId: actualEditor.operatorUserId.trim(),
        parameters: latestLock.parameterDefinitions.map((definition) => {
          const observation = actualEditor.parameters[definition.key] ?? {
            state: "not_measured" as const,
            value: "",
          };
          return observation.state === "measured"
            ? {
                definitionKey: definition.key,
                observedAt: utcInstant(actualEditor.executionStartedAt),
                source: "manual" as const,
                state: "measured" as const,
                unit: definition.unit,
                value: observation.value.trim(),
              }
            : {
                definitionKey: definition.key,
                observedAt: null,
                source: null,
                state: "not_measured" as const,
                unit: null,
                value: null,
              };
        }),
        reason,
        resources: [
          {
            kind: "machine" as const,
            label: actualEditor.resourceLabel.trim(),
            sourceObjectId: actualEditor.resourceSourceObjectId.trim(),
            sourceSystem: actualEditor.resourceSourceSystem,
          },
        ],
      };
      if (latestActual) {
        const commandValue: AppendTrialActualRevisionCommand = {
          ...actualContext,
          expectedActualRevisionGlobalId: latestActual.globalId,
          expectedActualVersion: latestActual.actualVersion,
          expectedRoundOptimisticVersion: round.optimisticVersion,
        };
        runExecutionCommand(t("Appending Trial Actual revision"), () =>
          dataSource.appendActualRevision(
            projectId,
            round.globalId,
            commandValue,
            context,
          ),
        );
      } else {
        const commandValue: StartTrialRoundCommand = {
          ...actualContext,
          expectedInputLockRevisionGlobalId: latestLock.globalId,
          expectedInputLockVersion: latestLock.lockVersion,
          expectedRoundOptimisticVersion: round.optimisticVersion,
        };
        runExecutionCommand(t("Starting Trial Round"), () =>
          dataSource.startRound(
            projectId,
            round.globalId,
            commandValue,
            context,
          ),
        );
      }
      return;
    }
    if (
      (editorKind === "create_sample" || editorKind === "revise_sample") &&
      latestLock
    ) {
      const context = contextFor(
        editorKind === "create_sample"
          ? "trial-sample-create"
          : "trial-sample-revise",
      );
      if (!context) return;
      const sample = {
        cavityGlobalIds: cavityIds,
        destination: sampleEditor.destination.trim(),
        feedbackObservedAt: sampleEditor.feedbackObservedAt
          ? utcInstant(sampleEditor.feedbackObservedAt)
          : null,
        feedbackSource: sampleEditor.feedbackSource.trim() || null,
        feedbackText: sampleEditor.feedbackText.trim() || null,
        label: sampleEditor.label.trim(),
        packaging: sampleEditor.packaging.trim(),
        quantity: Number(sampleEditor.quantity),
        unit: sampleEditor.unit.trim(),
      };
      if (editorKind === "create_sample") {
        const commandValue: CreateTrialSampleBatchCommand = {
          expectedInputLockRevisionGlobalId: latestLock.globalId,
          expectedRoundOptimisticVersion: round.optimisticVersion,
          reason,
          sample,
        };
        runExecutionCommand(t("Creating Sample Batch"), () =>
          dataSource.createSampleBatch(
            projectId,
            round.globalId,
            commandValue,
            context,
          ),
        );
      } else if (
        sampleEditor.revisionGlobalId &&
        sampleEditor.sampleBatchGlobalId &&
        sampleEditor.sampleVersion
      ) {
        const commandValue: AppendTrialSampleBatchRevisionCommand = {
          expectedRevisionGlobalId: sampleEditor.revisionGlobalId,
          expectedRoundOptimisticVersion: round.optimisticVersion,
          expectedSampleVersion: sampleEditor.sampleVersion,
          reason,
          sample,
        };
        runExecutionCommand(t("Appending Sample Batch revision"), () =>
          dataSource.appendSampleBatchRevision(
            projectId,
            round.globalId,
            sampleEditor.sampleBatchGlobalId ?? "",
            commandValue,
            context,
          ),
        );
      }
    }
  };

  const uploadSelectedFile = (): void => {
    if (!selectedFile || !sessionCommandContext) return;
    const context = contextFor("trial-evidence-upload");
    if (!context) return;
    runExecutionCommand(t("Uploading private Trial file"), () =>
      dataSource.uploadEvidenceFile(
        projectId,
        workspace.round.globalId,
        {
          expectedRoundOptimisticVersion: workspace.round.optimisticVersion,
          file: selectedFile,
        },
        context,
      ),
    );
  };

  const bindSelectedEvidence = (): void => {
    if (!bindFileId || !sessionCommandContext) return;
    const file = workspace.pendingFiles.find(
      (candidate) => candidate.globalId === bindFileId,
    );
    if (file?.scanState !== "clean") return;
    const sample = workspace.sampleBatchRevisions.find(
      (candidate) => candidate.globalId === bindSampleRevisionId,
    );
    const commandValue: BindTrialEvidenceCommand = {
      expectedFileOptimisticVersion: file.optimisticVersion,
      expectedRoundOptimisticVersion: workspace.round.optimisticVersion,
      fileRevisionGlobalId: file.globalId,
      role: bindRole,
      ...(sample
        ? {
            expectedSampleVersion: sample.sampleVersion,
            sampleBatchRevisionGlobalId: sample.globalId,
          }
        : {}),
    };
    const context = contextFor("trial-evidence-bind");
    if (!context) return;
    runExecutionCommand(t("Binding clean Trial evidence"), () =>
      dataSource.bindEvidence(
        projectId,
        workspace.round.globalId,
        commandValue,
        context,
      ),
    );
  };

  const downloadEvidence = (evidence: TrialEvidenceReference): void => {
    if (!sessionCommandContext) return;
    setCommand({
      kind: "processing",
      label: t("Preparing secure evidence download"),
    });
    const controller = new AbortController();
    void dataSource
      .downloadEvidence(projectId, workspace.round.globalId, evidence, {
        csrfToken: sessionCommandContext.csrfToken,
        signal: controller.signal,
      })
      .then((result) => {
        const url = URL.createObjectURL(result.blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = result.fileName;
        anchor.click();
        URL.revokeObjectURL(url);
        setCommand({
          kind: "succeeded",
          label: t("Private Trial evidence downloaded"),
          replayed: false,
        });
      })
      .catch((error: unknown) => {
        setCommand({ kind: "failed", failure: toRequestFailure(error) });
      });
  };

  const primaryKind = workspace.permissions.canPrepare
    ? "prepare"
    : workspace.permissions.canStart || workspace.permissions.canRecordActual
      ? "actual"
      : null;
  const primaryLabel = workspace.permissions.canPrepare
    ? t("Prepare Trial Round")
    : workspace.permissions.canStart
      ? t("Start Trial Round")
      : workspace.permissions.canRecordActual
        ? t("Append actual revision")
        : null;

  return (
    <>
      <Panel title={t("Trial Round execution")}>
        <div className="trial-live__command-bar">
          {primaryKind && primaryLabel ? (
            <Button
              disabled={!sessionCommandContext || processing}
              id="trial-execution-primary-action"
              onClick={(event) => {
                openEditor(primaryKind, event.currentTarget);
              }}
              visual="primary"
            >
              {primaryLabel}
            </Button>
          ) : null}
          {workspace.permissions.canManageSamples ? (
            <Button
              disabled={!sessionCommandContext || processing}
              onClick={(event) => {
                openEditor("create_sample", event.currentTarget);
              }}
            >
              {t("Create Sample Batch")}
            </Button>
          ) : null}
          {workspace.permissions.canManageEvidence ? (
            <Button
              disabled={!sessionCommandContext || processing}
              onClick={(event) => {
                openEditor("upload", event.currentTarget);
              }}
            >
              {t("Upload private evidence file")}
            </Button>
          ) : null}
        </div>
        <DefinitionList
          rows={[
            {
              label: t("Round"),
              value: workspace.round.displayLabel,
              exempt: "identifier",
            },
            {
              label: t("State"),
              value: roundStateLabel(t, workspace.round.currentState),
            },
            {
              label: t("Round version"),
              value: formatNumber(locale, workspace.round.optimisticVersion, 0),
            },
            {
              label: t("Input lock version"),
              value: latestLock
                ? formatNumber(locale, latestLock.lockVersion, 0)
                : t("Not prepared"),
            },
            {
              label: t("Actual revision"),
              value: latestActual
                ? formatNumber(locale, latestActual.actualVersion, 0)
                : t("Not started"),
            },
          ]}
        />
      </Panel>
      {!sessionCommandContext &&
      Object.values(workspace.permissions).some(Boolean) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Trial execution is read only in this session.")}</span>
          <span>
            {t(
              "Session verification is required before an execution command can be submitted.",
            )}
          </span>
        </div>
      ) : null}
      {Object.values(workspace.permissions).every((allowed) => !allowed) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Trial execution is read only for this Round.")}</span>
          <span>
            {t(
              "The current Round state and server permissions allow no execution command.",
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
            {t(
              "The exact execution command is being verified and committed atomically.",
            )}
          </span>
        </div>
      ) : null}
      {command.kind === "succeeded" ? (
        <div className="scenario-banner scenario-banner--queued" role="status">
          <span>{command.label}</span>
          <span>
            {command.replayed
              ? t(
                  "The exact prior execution command response was replayed safely.",
                )
              : t(
                  "The execution command completed with immutable audit truth.",
                )}
          </span>
        </div>
      ) : null}
      {command.kind === "failed" ? (
        <Panel title={t("Trial execution command not completed")}>
          <RequestFailurePanel failure={command.failure} />
          {canRetry(command.failure) ? (
            <Button onClick={() => latestCommand.current?.()}>
              {t("Retry exact command")}
            </Button>
          ) : null}
        </Panel>
      ) : null}
      {editorKind === "prepare" ? (
        <Panel title={t("Prepare exact locked inputs")}>
          <form
            className="trial-live__execution-form"
            onSubmit={(event) => {
              event.preventDefault();
              reviewExecution();
            }}
          >
            <fieldset className="trial-live__execution-fieldset trial-live__editor-wide">
              <legend>{t("Required released references")}</legend>
              <table
                aria-label={t("Required released references")}
                className="data-table"
              >
                <thead>
                  <tr>
                    <th>{t("Reference kind")}</th>
                    <th>{t("Stable ID")}</th>
                    <th>{t("Version")}</th>
                  </tr>
                </thead>
                <tbody>
                  {trialLockedReferenceKinds.map((kind, index) => (
                    <tr key={kind}>
                      <td>{referenceKindLabel(t, kind)}</td>
                      <td>
                        <TextInput
                          aria-label={t("{{kind}} stable ID", {
                            kind: referenceKindLabel(t, kind),
                          })}
                          disabled={processing}
                          onChange={(event) => {
                            setPrepareEditor((current) => ({
                              ...current,
                              references: {
                                ...current.references,
                                [kind]: {
                                  ...current.references[kind],
                                  globalId: event.target.value,
                                },
                              },
                            }));
                          }}
                          ref={index === 0 ? firstControl : undefined}
                          value={prepareEditor.references[kind].globalId}
                        />
                      </td>
                      <td>
                        <TextInput
                          aria-label={t("{{kind}} version", {
                            kind: referenceKindLabel(t, kind),
                          })}
                          disabled={processing}
                          min="1"
                          onChange={(event) => {
                            setPrepareEditor((current) => ({
                              ...current,
                              references: {
                                ...current.references,
                                [kind]: {
                                  ...current.references[kind],
                                  optimisticVersion: event.target.value,
                                },
                              },
                            }));
                          }}
                          type="number"
                          value={
                            prepareEditor.references[kind].optimisticVersion
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </fieldset>
            <fieldset className="trial-live__execution-fieldset trial-live__editor-wide">
              <legend>{t("Observed material identity")}</legend>
              <div className="trial-live__execution-grid">
                <label>
                  <span>{t("Source system")}</span>
                  <Select
                    aria-label={t("Material source system")}
                    disabled={processing}
                    onChange={(event) => {
                      setPrepareEditor((current) => ({
                        ...current,
                        materialSourceSystem: event.target.value as
                          | "NPI_ONE"
                          | "ERPNEXT",
                      }));
                    }}
                    value={prepareEditor.materialSourceSystem}
                  >
                    <option value="NPI_ONE">{t("NPI One")}</option>
                    <option data-language-exempt="identifier" value="ERPNEXT">
                      ERPNext
                    </option>
                  </Select>
                </label>
                {(
                  [
                    ["materialSourceObjectId", t("Material source object ID")],
                    ["materialLotBatchCode", t("Lot or batch code")],
                    ["materialLabel", t("Material label")],
                    ["materialColor", t("Material color")],
                    ["materialAdditive", t("Material additive")],
                  ] as const
                ).map(([field, label]) => (
                  <label key={field}>
                    <span>{label}</span>
                    <TextInput
                      aria-label={label}
                      disabled={processing}
                      onChange={(event) => {
                        setPrepareEditor((current) => ({
                          ...current,
                          [field]: event.target.value,
                        }));
                      }}
                      value={prepareEditor[field]}
                    />
                  </label>
                ))}
                <label>
                  <span>{t("Observed at (UTC)")}</span>
                  <TextInput
                    aria-label={t("Material observed at (UTC)")}
                    disabled={processing}
                    onChange={(event) => {
                      setPrepareEditor((current) => ({
                        ...current,
                        materialObservedAt: event.target.value,
                      }));
                    }}
                    type="datetime-local"
                    value={prepareEditor.materialObservedAt}
                  />
                </label>
              </div>
            </fieldset>
            <fieldset className="trial-live__execution-fieldset trial-live__editor-wide">
              <legend>{t("Parameter definitions")}</legend>
              <table
                aria-label={t("Parameter definitions")}
                className="data-table"
              >
                <thead>
                  <tr>
                    <th>{t("Key")}</th>
                    <th>{t("Category")}</th>
                    <th>{t("Value kind")}</th>
                    <th>{t("Unit")}</th>
                    <th>{t("Target")}</th>
                    <th>{t("Limits")}</th>
                    <th>{t("Required")}</th>
                    <th>{t("Actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {prepareEditor.definitions.map((definition, index) => (
                    <tr key={`${String(index)}-${definition.key}`}>
                      <td>
                        <TextInput
                          aria-label={t("Parameter {{index}} key", {
                            index: index + 1,
                          })}
                          disabled={processing}
                          onChange={(event) => {
                            setPrepareEditor((current) => ({
                              ...current,
                              definitions: current.definitions.map(
                                (item, itemIndex) =>
                                  itemIndex === index
                                    ? { ...item, key: event.target.value }
                                    : item,
                              ),
                            }));
                          }}
                          value={definition.key}
                        />
                      </td>
                      <td>
                        <TextInput
                          aria-label={t("Parameter {{index}} category", {
                            index: index + 1,
                          })}
                          disabled={processing}
                          onChange={(event) => {
                            setPrepareEditor((current) => ({
                              ...current,
                              definitions: current.definitions.map(
                                (item, itemIndex) =>
                                  itemIndex === index
                                    ? { ...item, category: event.target.value }
                                    : item,
                              ),
                            }));
                          }}
                          value={definition.category}
                        />
                      </td>
                      <td>
                        <Select
                          aria-label={t("Parameter {{index}} value kind", {
                            index: index + 1,
                          })}
                          disabled={processing}
                          onChange={(event) => {
                            setPrepareEditor((current) => ({
                              ...current,
                              definitions: current.definitions.map(
                                (item, itemIndex) =>
                                  itemIndex === index
                                    ? {
                                        ...item,
                                        valueKind: event.target
                                          .value as TrialParameterValueKind,
                                      }
                                    : item,
                              ),
                            }));
                          }}
                          value={definition.valueKind}
                        >
                          {trialParameterValueKinds.map((kind) => (
                            <option key={kind} value={kind}>
                              {kind === "decimal"
                                ? t("Decimal")
                                : kind === "integer"
                                  ? t("Integer")
                                  : kind === "text"
                                    ? t("Text")
                                    : t("Boolean")}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td>
                        <TextInput
                          aria-label={t("Parameter {{index}} unit", {
                            index: index + 1,
                          })}
                          disabled={processing}
                          onChange={(event) => {
                            setPrepareEditor((current) => ({
                              ...current,
                              definitions: current.definitions.map(
                                (item, itemIndex) =>
                                  itemIndex === index
                                    ? { ...item, unit: event.target.value }
                                    : item,
                              ),
                            }));
                          }}
                          value={definition.unit}
                        />
                      </td>
                      <td>
                        <TextInput
                          aria-label={t("Parameter {{index}} target", {
                            index: index + 1,
                          })}
                          disabled={processing}
                          onChange={(event) => {
                            setPrepareEditor((current) => ({
                              ...current,
                              definitions: current.definitions.map(
                                (item, itemIndex) =>
                                  itemIndex === index
                                    ? {
                                        ...item,
                                        targetValue: event.target.value,
                                      }
                                    : item,
                              ),
                            }));
                          }}
                          value={definition.targetValue}
                        />
                      </td>
                      <td>
                        <div className="trial-live__limit-inputs">
                          <TextInput
                            aria-label={t("Parameter {{index}} lower limit", {
                              index: index + 1,
                            })}
                            disabled={processing}
                            onChange={(event) => {
                              setPrepareEditor((current) => ({
                                ...current,
                                definitions: current.definitions.map(
                                  (item, itemIndex) =>
                                    itemIndex === index
                                      ? {
                                          ...item,
                                          lowerLimit: event.target.value,
                                        }
                                      : item,
                                ),
                              }));
                            }}
                            value={definition.lowerLimit}
                          />
                          <TextInput
                            aria-label={t("Parameter {{index}} upper limit", {
                              index: index + 1,
                            })}
                            disabled={processing}
                            onChange={(event) => {
                              setPrepareEditor((current) => ({
                                ...current,
                                definitions: current.definitions.map(
                                  (item, itemIndex) =>
                                    itemIndex === index
                                      ? {
                                          ...item,
                                          upperLimit: event.target.value,
                                        }
                                      : item,
                                ),
                              }));
                            }}
                            value={definition.upperLimit}
                          />
                        </div>
                      </td>
                      <td>
                        <input
                          aria-label={t("Parameter {{index}} required", {
                            index: index + 1,
                          })}
                          checked={definition.required}
                          disabled={processing}
                          onChange={(event) => {
                            setPrepareEditor((current) => ({
                              ...current,
                              definitions: current.definitions.map(
                                (item, itemIndex) =>
                                  itemIndex === index
                                    ? {
                                        ...item,
                                        required: event.target.checked,
                                      }
                                    : item,
                              ),
                            }));
                          }}
                          type="checkbox"
                        />
                      </td>
                      <td>
                        <Button
                          disabled={
                            processing || prepareEditor.definitions.length === 1
                          }
                          onClick={() => {
                            setPrepareEditor((current) => ({
                              ...current,
                              definitions: current.definitions.filter(
                                (_item, itemIndex) => itemIndex !== index,
                              ),
                            }));
                          }}
                          type="button"
                        >
                          {t("Remove")}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Button
                disabled={processing || prepareEditor.definitions.length >= 250}
                onClick={() => {
                  setPrepareEditor((current) => ({
                    ...current,
                    definitions: [
                      ...current.definitions,
                      {
                        category: "",
                        key: "",
                        lowerLimit: "",
                        required: true,
                        targetValue: "",
                        unit: "",
                        upperLimit: "",
                        valueKind: "decimal",
                      },
                    ],
                  }));
                }}
                type="button"
              >
                {t("Add parameter")}
              </Button>
            </fieldset>
            {formError ? (
              <p className="form-error trial-live__editor-wide" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions trial-live__editor-wide">
              <Button disabled={processing} type="submit" visual="primary">
                {t("Review command")}
              </Button>
              <Button disabled={processing} onClick={closeEditor} type="button">
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}
      {editorKind === "actual" && latestLock ? (
        <Panel
          title={
            latestActual ? t("Append actual revision") : t("Start Trial Round")
          }
        >
          <form
            className="trial-live__execution-form"
            onSubmit={(event) => {
              event.preventDefault();
              reviewExecution();
            }}
          >
            <fieldset className="trial-live__execution-fieldset">
              <legend>{t("Confirmed machine")}</legend>
              <Select
                aria-label={t("Machine source system")}
                disabled={processing}
                onChange={(event) => {
                  setActualEditor((current) => ({
                    ...current,
                    resourceSourceSystem: event.target.value as
                      | "NPI_ONE"
                      | "ERPNEXT",
                  }));
                }}
                value={actualEditor.resourceSourceSystem}
              >
                <option value="NPI_ONE">{t("NPI One")}</option>
                <option data-language-exempt="identifier" value="ERPNEXT">
                  ERPNext
                </option>
              </Select>
              <TextInput
                aria-label={t("Actual machine source object ID")}
                disabled={processing}
                onChange={(event) => {
                  setActualEditor((current) => ({
                    ...current,
                    resourceSourceObjectId: event.target.value,
                  }));
                }}
                ref={firstControl}
                value={actualEditor.resourceSourceObjectId}
              />
              <TextInput
                aria-label={t("Actual machine label")}
                disabled={processing}
                onChange={(event) => {
                  setActualEditor((current) => ({
                    ...current,
                    resourceLabel: event.target.value,
                  }));
                }}
                value={actualEditor.resourceLabel}
              />
              <SemanticStatus
                label={t("ERP verification unavailable")}
                tone="warning"
              />
            </fieldset>
            <fieldset className="trial-live__execution-fieldset">
              <legend>{t("Execution context")}</legend>
              <label>
                <span>{t("Operator user")}</span>
                <TextInput
                  aria-label={t("Operator user")}
                  disabled={processing}
                  onChange={(event) => {
                    setActualEditor((current) => ({
                      ...current,
                      operatorUserId: event.target.value,
                    }));
                  }}
                  value={actualEditor.operatorUserId}
                />
              </label>
              <label>
                <span>{t("Execution started at (UTC)")}</span>
                <TextInput
                  aria-label={t("Execution started at (UTC)")}
                  disabled={processing}
                  onChange={(event) => {
                    setActualEditor((current) => ({
                      ...current,
                      executionStartedAt: event.target.value,
                    }));
                  }}
                  type="datetime-local"
                  value={actualEditor.executionStartedAt}
                />
              </label>
              <label>
                <span>{t("Environment key")}</span>
                <TextInput
                  aria-label={t("Environment key")}
                  disabled={processing}
                  onChange={(event) => {
                    setActualEditor((current) => ({
                      ...current,
                      environmentKey: event.target.value,
                    }));
                  }}
                  value={actualEditor.environmentKey}
                />
              </label>
              <label>
                <span>{t("Environment value")}</span>
                <TextInput
                  aria-label={t("Environment value")}
                  disabled={processing}
                  onChange={(event) => {
                    setActualEditor((current) => ({
                      ...current,
                      environmentValue: event.target.value,
                    }));
                  }}
                  value={actualEditor.environmentValue}
                />
              </label>
              <label>
                <span>{t("Environment unit")}</span>
                <TextInput
                  aria-label={t("Environment unit")}
                  disabled={processing}
                  onChange={(event) => {
                    setActualEditor((current) => ({
                      ...current,
                      environmentUnit: event.target.value,
                    }));
                  }}
                  value={actualEditor.environmentUnit}
                />
              </label>
            </fieldset>
            <div className="trial-live__locked-material trial-live__editor-wide">
              <SemanticStatus label={t("Locked material")} tone="info" />
              <span data-language-exempt="business-data">
                {latestLock.material.label}
              </span>
              <span data-language-exempt="identifier">
                {latestLock.material.lotBatchCode}
              </span>
            </div>
            <fieldset className="trial-live__execution-fieldset trial-live__editor-wide">
              <legend>{t("Manual parameter observations")}</legend>
              <table
                aria-label={t("Manual parameter observations")}
                className="data-table"
              >
                <thead>
                  <tr>
                    <th>{t("Parameter")}</th>
                    <th>{t("Target and limits")}</th>
                    <th>{t("Measurement state")}</th>
                    <th>{t("Observed value")}</th>
                    <th>{t("Acquisition")}</th>
                  </tr>
                </thead>
                <tbody>
                  {latestLock.parameterDefinitions.map((definition) => {
                    const observation = actualEditor.parameters[
                      definition.key
                    ] ?? {
                      state: "not_measured" as const,
                      value: "",
                    };
                    return (
                      <tr key={definition.key}>
                        <td>
                          <strong data-language-exempt="identifier">
                            {definition.key}
                          </strong>
                          <small
                            className="trial-live__resource-reference"
                            data-language-exempt="business-data"
                          >
                            {definition.category}
                          </small>
                        </td>
                        <td data-language-exempt="business-data">
                          {definition.targetValue ?? "—"}{" "}
                          {definition.unit ?? ""}
                          {definition.lowerLimit && definition.upperLimit
                            ? ` (${definition.lowerLimit}–${definition.upperLimit})`
                            : ""}
                        </td>
                        <td>
                          <Select
                            aria-label={t("{{key}} measurement state", {
                              key: definition.key,
                            })}
                            disabled={processing}
                            onChange={(event) => {
                              setActualEditor((current) => ({
                                ...current,
                                parameters: {
                                  ...current.parameters,
                                  [definition.key]: {
                                    ...observation,
                                    state: event.target.value as
                                      | "measured"
                                      | "not_measured",
                                    ...(event.target.value === "not_measured"
                                      ? { value: "" }
                                      : {}),
                                  },
                                },
                              }));
                            }}
                            value={observation.state}
                          >
                            <option value="measured">{t("Measured")}</option>
                            <option value="not_measured">
                              {t("Not measured")}
                            </option>
                          </Select>
                        </td>
                        <td>
                          <TextInput
                            aria-label={t("{{key}} observed value", {
                              key: definition.key,
                            })}
                            disabled={
                              processing || observation.state === "not_measured"
                            }
                            onChange={(event) => {
                              setActualEditor((current) => ({
                                ...current,
                                parameters: {
                                  ...current.parameters,
                                  [definition.key]: {
                                    ...observation,
                                    value: event.target.value,
                                  },
                                },
                              }));
                            }}
                            value={observation.value}
                          />
                        </td>
                        <td>{t("Manual only")}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </fieldset>
            {formError ? (
              <p className="form-error trial-live__editor-wide" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions trial-live__editor-wide">
              <Button disabled={processing} type="submit" visual="primary">
                {t("Review command")}
              </Button>
              <Button disabled={processing} onClick={closeEditor} type="button">
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}
      {(editorKind === "create_sample" || editorKind === "revise_sample") &&
      latestLock ? (
        <Panel
          title={
            editorKind === "create_sample"
              ? t("Create Sample Batch")
              : t("Append Sample Batch revision")
          }
        >
          <form
            className="trial-live__execution-form"
            onSubmit={(event) => {
              event.preventDefault();
              reviewExecution();
            }}
          >
            {[
              ["label", t("Sample label")],
              ["cavityGlobalIds", t("Cavity stable IDs")],
              ["quantity", t("Quantity")],
              ["unit", t("Unit")],
              ["packaging", t("Packaging")],
              ["destination", t("Destination")],
              ["feedbackSource", t("Feedback source")],
            ].map(([field, label], index) => {
              const lockedSuccessor =
                editorKind === "revise_sample" &&
                ["label", "cavityGlobalIds", "quantity", "unit"].includes(
                  field ?? "",
                );
              return (
                <label key={field}>
                  <span>{label}</span>
                  <TextInput
                    aria-label={label}
                    disabled={processing || lockedSuccessor}
                    onChange={(event) => {
                      setSampleEditor((current) => ({
                        ...current,
                        [field ?? "label"]: event.target.value,
                      }));
                    }}
                    ref={index === 0 ? firstControl : undefined}
                    type={field === "quantity" ? "number" : "text"}
                    value={String(
                      sampleEditor[field as keyof SampleEditorState] ?? "",
                    )}
                  />
                </label>
              );
            })}
            <label className="trial-live__editor-wide">
              <span>{t("Feedback observation")}</span>
              <textarea
                aria-label={t("Feedback observation")}
                disabled={processing}
                maxLength={4000}
                onChange={(event) => {
                  setSampleEditor((current) => ({
                    ...current,
                    feedbackText: event.target.value,
                  }));
                }}
                rows={3}
                value={sampleEditor.feedbackText}
              />
            </label>
            <label>
              <span>{t("Feedback observed at (UTC)")}</span>
              <TextInput
                aria-label={t("Feedback observed at (UTC)")}
                disabled={processing}
                onChange={(event) => {
                  setSampleEditor((current) => ({
                    ...current,
                    feedbackObservedAt: event.target.value,
                  }));
                }}
                type="datetime-local"
                value={sampleEditor.feedbackObservedAt}
              />
            </label>
            <p className="context-help trial-live__editor-wide">
              {editorKind === "revise_sample"
                ? t(
                    "Sample identity, cavities, material, quantity and unit remain locked across revisions.",
                  )
                : t(
                    "The Sample Batch is bound to the exact prepared material and selected cavities.",
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
              <Button disabled={processing} onClick={closeEditor} type="button">
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}
      {editorKind === "upload" ? (
        <Panel title={t("Upload private evidence file")}>
          <div className="trial-live__upload-editor">
            <label>
              <span>{t("Evidence file")}</span>
              <input
                accept="image/*,video/*,.csv,.pdf"
                aria-label={t("Evidence file")}
                disabled={processing}
                onChange={(event) => {
                  setSelectedFile(event.target.files?.[0] ?? null);
                }}
                ref={firstControl}
                type="file"
              />
            </label>
            <div className="blocking-message failure-explanation">
              <SemanticStatus
                label={t("Private and pending scan")}
                tone="warning"
              />
              <p>
                {t(
                  "Upload registers a private pending File Revision only. It is not evidence until a clean scan result is bound separately.",
                )}
              </p>
            </div>
            <div className="detail-actions">
              <Button
                disabled={!selectedFile || processing}
                onClick={uploadSelectedFile}
                visual="primary"
              >
                {t("Upload pending file")}
              </Button>
              <Button disabled={processing} onClick={closeEditor}>
                {t("Cancel")}
              </Button>
            </div>
          </div>
        </Panel>
      ) : null}
      {editorKind === "bind_evidence" && bindFileId ? (
        <Panel title={t("Bind clean Trial evidence")}>
          <div className="trial-live__execution-form">
            <label>
              <span>{t("Evidence role")}</span>
              <Select
                aria-label={t("Evidence role")}
                disabled={processing}
                onChange={(event) => {
                  setBindRole(event.target.value as TrialEvidenceRole);
                }}
                value={bindRole}
              >
                {trialEvidenceRoles.map((role) => (
                  <option key={role} value={role}>
                    {evidenceRoleLabel(t, role)}
                  </option>
                ))}
              </Select>
            </label>
            <label>
              <span>{t("Related Sample Batch revision")}</span>
              <Select
                aria-label={t("Related Sample Batch revision")}
                disabled={processing}
                onChange={(event) => {
                  setBindSampleRevisionId(event.target.value);
                }}
                value={bindSampleRevisionId}
              >
                <option value="">{t("Round evidence only")}</option>
                {workspace.sampleBatchRevisions.map((sample) => (
                  <option key={sample.globalId} value={sample.globalId}>
                    {t("{{sample}} · Version {{version}}", {
                      sample: sample.label,
                      version: sample.sampleVersion,
                    })}
                  </option>
                ))}
              </Select>
            </label>
            <p className="context-help trial-live__editor-wide">
              {t(
                "The server rechecks the exact clean private File Revision and optional Sample Batch version before binding.",
              )}
            </p>
            <div className="detail-actions trial-live__editor-wide">
              <Button
                disabled={processing}
                onClick={bindSelectedEvidence}
                visual="primary"
              >
                {t("Bind clean evidence")}
              </Button>
              <Button disabled={processing} onClick={closeEditor}>
                {t("Cancel")}
              </Button>
            </div>
          </div>
        </Panel>
      ) : null}
      <Panel title={t("Locked preparation inputs")}>
        {latestLock ? (
          <>
            <DefinitionList
              rows={[
                {
                  label: t("Lock revision"),
                  value: formatNumber(locale, latestLock.lockVersion, 0),
                },
                {
                  label: t("Lock snapshot"),
                  value: latestLock.snapshotHash,
                  exempt: "identifier",
                },
                {
                  label: t("Material"),
                  value: latestLock.material.label,
                  exempt: "business-data",
                },
                {
                  label: t("Lot or batch code"),
                  value: latestLock.material.lotBatchCode,
                  exempt: "identifier",
                },
                { label: t("ERP verification"), value: t("Unavailable") },
              ]}
            />
            <table
              aria-label={t("Locked released references")}
              className="data-table"
              tabIndex={0}
            >
              <thead>
                <tr>
                  <th>{t("Reference kind")}</th>
                  <th>{t("Stable ID")}</th>
                  <th>{t("Version")}</th>
                  <th>{t("Snapshot")}</th>
                </tr>
              </thead>
              <tbody>
                {latestLock.references.map((reference) => (
                  <tr key={`${reference.kind}-${reference.globalId}`}>
                    <td>{referenceKindLabel(t, reference.kind)}</td>
                    <td data-language-exempt="identifier">
                      {reference.globalId}
                    </td>
                    <td>
                      {formatNumber(locale, reference.optimisticVersion, 0)}
                    </td>
                    <td
                      className="trial-live__hash"
                      data-language-exempt="identifier"
                    >
                      {reference.snapshotHash}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <div className="empty-state" role="status">
            <strong>
              {t("This planned Round has no locked input revision.")}
            </strong>
            <span>
              {t(
                "Prepare the exact eight released reference kinds, observed material and parameter definitions before execution.",
              )}
            </span>
          </div>
        )}
      </Panel>
      <Panel title={t("Actual process parameters")}>
        {latestActual ? (
          <table
            aria-label={t("Actual process parameters")}
            className="data-table"
            tabIndex={0}
          >
            <thead>
              <tr>
                <th>{t("Parameter")}</th>
                <th>{t("State")}</th>
                <th>{t("Value")}</th>
                <th>{t("Observed at")}</th>
                <th>{t("Source")}</th>
              </tr>
            </thead>
            <tbody>
              {latestActual.parameters.map((parameter) => (
                <tr key={parameter.definitionKey}>
                  <td data-language-exempt="identifier">
                    {parameter.definitionKey}
                  </td>
                  <td>
                    <SemanticStatus
                      label={
                        parameter.state === "measured"
                          ? t("Measured")
                          : t("Not measured")
                      }
                      tone={parameter.state === "measured" ? "info" : "warning"}
                    />
                  </td>
                  <td data-language-exempt="business-data">
                    {parameter.value === null
                      ? "—"
                      : `${parameter.value} ${parameter.unit ?? ""}`}
                  </td>
                  <td>
                    {parameter.observedAt
                      ? formatDateTime(locale, parameter.observedAt)
                      : "—"}
                  </td>
                  <td>
                    {parameter.source === "manual"
                      ? t("Manual")
                      : t("Unavailable")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state" role="status">
            <strong>
              {t("No actual execution revision has been recorded.")}
            </strong>
            <span>
              {t(
                "Starting the prepared Round records the first complete manual actual context.",
              )}
            </span>
          </div>
        )}
        <div className="blocking-message failure-explanation">
          <SemanticStatus
            label={t("Machine import unavailable")}
            tone="warning"
          />
          <p>
            {t(
              "Parameters remain manual observations. No controller or ERP value is imported or presented as measured.",
            )}
          </p>
        </div>
      </Panel>
      <Panel title={t("Sample Batches")}>
        {workspace.sampleBatchRevisions.length ? (
          <table
            aria-label={t("Sample Batches")}
            className="data-table"
            tabIndex={0}
          >
            <thead>
              <tr>
                <th>{t("Sample")}</th>
                <th>{t("Version")}</th>
                <th>{t("Cavities")}</th>
                <th>{t("Quantity")}</th>
                <th>{t("Destination")}</th>
                <th>{t("Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {workspace.sampleBatchRevisions.map((sample) => (
                <tr key={sample.globalId}>
                  <td data-language-exempt="identifier">{sample.label}</td>
                  <td>{formatNumber(locale, sample.sampleVersion, 0)}</td>
                  <td data-language-exempt="identifier">
                    {sample.cavityGlobalIds.join(", ")}
                  </td>
                  <td data-language-exempt="business-data">
                    {formatNumber(locale, sample.quantity, 0)} {sample.unit}
                  </td>
                  <td data-language-exempt="business-data">
                    {sample.destination}
                  </td>
                  <td>
                    {workspace.permissions.canManageSamples ? (
                      <Button
                        disabled={
                          !sessionCommandContext ||
                          processing ||
                          workspace.sampleBatchRevisions.some(
                            (candidate) =>
                              candidate.sampleBatchGlobalId ===
                                sample.sampleBatchGlobalId &&
                              candidate.sampleVersion > sample.sampleVersion,
                          )
                        }
                        onClick={(event) => {
                          openEditor(
                            "revise_sample",
                            event.currentTarget,
                            sample.globalId,
                          );
                        }}
                      >
                        {t("Append revision")}
                      </Button>
                    ) : (
                      t("Read only")
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state" role="status">
            <strong>
              {t("No Sample Batch has been recorded for this Round.")}
            </strong>
            <span>
              {t(
                "Record stable sample identity, all cavities, quantity, packaging and destination during a running Round.",
              )}
            </span>
          </div>
        )}
      </Panel>
      <Panel title={t("Private files awaiting evidence binding")}>
        {workspace.pendingFiles.length ? (
          <table
            aria-label={t("Private files awaiting evidence binding")}
            className="data-table"
            tabIndex={0}
          >
            <thead>
              <tr>
                <th>{t("File")}</th>
                <th>{t("Size")}</th>
                <th>{t("Scan state")}</th>
                <th>{t("Privacy")}</th>
                <th>{t("Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {workspace.pendingFiles.map((file) => (
                <tr key={file.globalId}>
                  <td>
                    <span data-language-exempt="filename">{file.fileName}</span>
                    <small
                      className="trial-live__resource-reference"
                      data-language-exempt="identifier"
                    >
                      {file.globalId}
                    </small>
                  </td>
                  <td>
                    {t("{{size}} B", {
                      size: formatNumber(locale, file.sizeBytes, 0),
                    })}
                  </td>
                  <td>
                    <SemanticStatus
                      label={
                        file.scanState === "pending"
                          ? t("Pending scan")
                          : file.scanState === "clean"
                            ? t("Clean")
                            : file.scanState === "infected"
                              ? t("Infected")
                              : t("Scan failed")
                      }
                      tone={file.scanState === "clean" ? "info" : "warning"}
                    />
                  </td>
                  <td>{t("Private")}</td>
                  <td>
                    <Button
                      disabled={
                        !sessionCommandContext ||
                        processing ||
                        file.scanState !== "clean" ||
                        !workspace.permissions.canManageEvidence
                      }
                      onClick={(event) => {
                        setBindFileId(file.globalId);
                        setBindRole("photo");
                        setBindSampleRevisionId("");
                        openEditor("bind_evidence", event.currentTarget);
                        setBindFileId(file.globalId);
                      }}
                    >
                      {t("Bind as evidence")}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>{t("No private uploaded file is awaiting evidence binding.")}</p>
        )}
      </Panel>
      <Panel title={t("Controlled Trial evidence")}>
        {workspace.evidence.length ? (
          <table
            aria-label={t("Controlled Trial evidence")}
            className="data-table"
            tabIndex={0}
          >
            <thead>
              <tr>
                <th>{t("Role")}</th>
                <th>{t("File revision")}</th>
                <th>{t("Sample revision")}</th>
                <th>{t("Integrity")}</th>
                <th>{t("Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {workspace.evidence.map((evidence) => (
                <tr key={evidence.globalId}>
                  <td>{evidenceRoleLabel(t, evidence.role)}</td>
                  <td data-language-exempt="identifier">
                    {evidence.fileRevisionGlobalId}
                  </td>
                  <td data-language-exempt="identifier">
                    {evidence.sampleBatchRevisionGlobalId ?? "—"}
                  </td>
                  <td>
                    <SemanticStatus
                      label={t("Clean and private")}
                      tone="info"
                    />
                    <small
                      className="trial-live__resource-reference"
                      data-language-exempt="identifier"
                    >
                      {evidence.fileSha256}
                    </small>
                  </td>
                  <td>
                    <Button
                      disabled={!sessionCommandContext || processing}
                      onClick={() => {
                        downloadEvidence(evidence);
                      }}
                    >
                      {t("Download audited bytes")}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state" role="status">
            <strong>
              {t("No clean evidence has been bound to this Round.")}
            </strong>
            <span>
              {t(
                "Upload, scan and bind are separate; a pending or failed file is never presented as evidence.",
              )}
            </span>
          </div>
        )}
      </Panel>
      <Panel title={t("Execution completeness and unavailable capabilities")}>
        <div className="trial-live__truth-grid">
          <div className="trial-live__truth-section">
            <strong>{t("Missing execution facts")}</strong>
            {workspace.missingFacts.length ? (
              <ul>
                {workspace.missingFacts.map((fact) => (
                  <li key={fact}>{missingFactLabel(t, fact)}</li>
                ))}
              </ul>
            ) : (
              <SemanticStatus
                label={t("No missing execution fact")}
                tone="info"
              />
            )}
          </div>
          <div className="trial-live__truth-section">
            <strong>{t("Unavailable in this checkpoint")}</strong>
            <ul>
              <li>{t("Machine parameter import")}</li>
              <li>{t("ERP formal quality results")}</li>
              <li>{t("Conclusion and Gate effect")}</li>
              <li>{t("Approved Trial baseline")}</li>
            </ul>
          </div>
        </div>
      </Panel>
      {reviewOpen && editorKind ? (
        <ImpactReview
          confirmLabel={
            editorKind === "prepare"
              ? t("Prepare Trial Round")
              : editorKind === "actual"
                ? latestActual
                  ? t("Append actual revision")
                  : t("Start Trial Round")
                : editorKind === "create_sample"
                  ? t("Create Sample Batch")
                  : t("Append Sample Batch revision")
          }
          details={{
            objectIdentity: workspace.round.globalId,
            version: `v${String(workspace.round.optimisticVersion)}`,
            impact:
              editorKind === "prepare"
                ? t(
                    "Freezes exact released references, observed material and parameter definitions before execution.",
                  )
                : editorKind === "actual"
                  ? t(
                      "Appends a manual immutable actual context against the exact prepared input lock.",
                    )
                  : t(
                      "Appends immutable Sample Batch history without rewriting its stable identity or cavities.",
                    ),
            permission: t(
              "The server rechecks Project membership, internal role and current Round-state authority.",
            ),
            irreversible: t(
              "Committed execution history is immutable and cannot be edited through generic CRUD.",
            ),
            failureHandling: t(
              "A failed command changes no execution row and can be retried with the same exact request.",
            ),
            audit: t(
              "The command records actor, request, trace, reason and immutable snapshot evidence.",
            ),
          }}
          onCancel={() => {
            setReviewOpen(false);
          }}
          onConfirm={confirmExecution}
          reasonMaxLength={500}
          returnFocusTarget={() => returnFocus.current}
          title={t("Review immutable Trial execution command")}
        />
      ) : null}
    </>
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
  const [executionAttempt, setExecutionAttempt] = useState(0);
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [selectedRoundId, setSelectedRoundId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DetailState>({ kind: "idle" });
  const [execution, setExecution] = useState<ExecutionState>({ kind: "idle" });
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const returnFocus = useRef<HTMLElement | null>(null);
  const firstEditorControl = useRef<HTMLInputElement | null>(null);
  const latestCommand = useRef<(() => void) | null>(null);
  const workspace = resource.kind === "loaded" ? resource.value : null;
  const planDetail = detail.kind === "loaded" ? detail.value : null;
  const executionWorkspace =
    execution.kind === "loaded" ? execution.value : null;

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
        const nextRoundId = value.rounds[0]?.globalId ?? null;
        setSelectedRoundId(nextRoundId);
        setExecution(nextRoundId ? { kind: "loading" } : { kind: "idle" });
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
    if (!selectedRoundId) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadRoundExecution(projectId, selectedRoundId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setExecution({ kind: "loaded", value });
        setDetail((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  rounds: current.value.rounds.map((round) =>
                    round.globalId === value.round.globalId
                      ? value.round
                      : round,
                  ),
                },
              }
            : current,
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof TrialRequestCancelledError
        )
          return;
        setExecution({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, executionAttempt, projectId, selectedRoundId]);

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
          workspace.permissions.canCreatePlan && workspace.plans.length === 0
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
          { id: "trial-live-execution", label: t("Trial Round execution") },
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
                    setSelectedRoundId(null);
                    setExecution({ kind: "idle" });
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
                {selectedPlanId === plan.planGlobalId && planDetail ? (
                  <ul className="trial-live__round-tree">
                    {planDetail.rounds.map((round) => (
                      <li key={round.globalId}>
                        <button
                          aria-current={selectedRoundId === round.globalId}
                          className="trial-live__round-control"
                          onClick={() => {
                            setSelectedRoundId(round.globalId);
                            setExecution({ kind: "loading" });
                          }}
                          type="button"
                        >
                          <span data-language-exempt="identifier">
                            {round.displayLabel}
                          </span>
                          <small>
                            {roundStateLabel(t, round.currentState)}
                          </small>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
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
                          <td>
                            <button
                              aria-current={selectedRoundId === round.globalId}
                              className="trial-live__round-link"
                              data-language-exempt="identifier"
                              onClick={() => {
                                setSelectedRoundId(round.globalId);
                                setExecution({ kind: "loading" });
                              }}
                              type="button"
                            >
                              {round.displayLabel}
                            </button>
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
              <div id="trial-live-execution" tabIndex={-1} />
              {execution.kind === "loading" ? <LoadingSurface /> : null}
              {execution.kind === "failed" ? (
                <Panel title={t("Trial execution workspace unavailable")}>
                  <RequestFailurePanel failure={execution.failure} />
                  {canRetry(execution.failure) ? (
                    <Button
                      onClick={() => {
                        setExecution({ kind: "loading" });
                        setExecutionAttempt((current) => current + 1);
                      }}
                    >
                      {t("Retry")}
                    </Button>
                  ) : null}
                </Panel>
              ) : null}
              {execution.kind === "loaded" ? (
                <TrialExecutionSection
                  dataSource={dataSource}
                  detail={planDetail}
                  onWorkspace={(value) => {
                    setExecution({ kind: "loaded", value });
                    setDetail((current) =>
                      current.kind === "loaded"
                        ? {
                            kind: "loaded",
                            value: {
                              ...current.value,
                              rounds: current.value.rounds.map((round) =>
                                round.globalId === value.round.globalId
                                  ? value.round
                                  : round,
                              ),
                            },
                          }
                        : current,
                    );
                  }}
                  projectId={projectId}
                  reportWorkspaceDirty={reportWorkspaceDirty}
                  workspace={execution.value}
                />
              ) : null}
              {selectedRoundId === null ? (
                <Panel title={t("Trial Round execution")}>
                  <div className="empty-state" role="status">
                    <strong>{t("No Trial Round is selected.")}</strong>
                    <span>
                      {t(
                        "Create or select a planned Trial Round before opening execution truth.",
                      )}
                    </span>
                  </div>
                </Panel>
              ) : null}
              <Panel title={t("Later Trial sections")}>
                <div
                  className="trial-live__later"
                  id="trial-live-later"
                  tabIndex={-1}
                >
                  {[
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
              {
                label: t("Selected Round"),
                value:
                  executionWorkspace?.round.displayLabel ??
                  t("No Round selected"),
                ...(executionWorkspace
                  ? { exempt: "identifier" as const }
                  : {}),
              },
              {
                label: t("Round state"),
                value: executionWorkspace
                  ? roundStateLabel(t, executionWorkspace.round.currentState)
                  : t("Unavailable"),
              },
              {
                label: t("Execution missing facts"),
                value: executionWorkspace
                  ? formatNumber(
                      locale,
                      executionWorkspace.missingFacts.length,
                      0,
                    )
                  : t("Unavailable"),
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
            <SemanticStatus
              label={t("Execution boundary active")}
              tone="info"
            />
            <p>
              {t(
                "P7-02 supports exact preparation, running actuals, Sample Batches and clean private evidence. Conclusion, Gate effect and formal ERP quality remain unavailable.",
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
