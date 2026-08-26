import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  trialEvidenceRoles,
  trialLockedReferenceKinds,
  trialParameterValueKinds,
  trialActionSeverities,
  trialConclusionCodes,
  trialPurposes,
  trialReviewReferenceKinds,
  TrialRequestCancelledError,
  type AppendTrialActualRevisionCommand,
  type AppendTrialSampleBatchRevisionCommand,
  type BindTrialEvidenceCommand,
  type BeginTrialAnalysisCommand,
  type CreateTrialRoundComparisonCommand,
  type CreateTrialReviewReferenceCommand,
  type CreateTrialCavityResultCommand,
  type CreateTrialDefectCommand,
  type CreatePlannedTrialRoundCommand,
  type CreateTrialSampleBatchCommand,
  type CreateTrialPlanCommand,
  type CreateTrialPlanRevisionCommand,
  type GenerateTrialPlanActionsCommand,
  type PrepareTrialRoundCommand,
  type StartTrialRoundCommand,
  type TrialActionSeverity,
  type TrialCommandResult,
  type TrialConclusionBlocker,
  type TrialConclusionCode,
  type TrialConclusionRevision,
  type TrialDataSource,
  type TrialEvidenceReference,
  type TrialEvidenceRole,
  type TrialExecutionCommandResult,
  type TrialExecutionWorkspace,
  type TrialDefectRevision,
  type TrialDefectSeverity,
  type TrialQualityCommandResult,
  type TrialQualityDefectRevision,
  type TrialQualityWorkspace,
  type TrialReviewCommandResult,
  type TrialReviewReferenceKind,
  type TrialReviewWorkspace,
  type TrialLockedReferenceKind,
  type TrialParameterValueKind,
  type TrialPlanDetail,
  type TrialPlanningWorkspace,
  type TrialPurpose,
  type TrialResourceProposalInput,
  type TrialRoundState,
  type TrialRoundSummary,
  type ReviseTrialCavityResultCommand,
  type ReviseTrialDefectCommand,
  type VerifyTrialDefectCommand,
  type DecideTrialConclusionCommand,
  type ReopenTrialConclusionCommand,
  type ReleasedTrialSummaryCommandResult,
  type ReleasedTrialSummaryFactGroup,
  type ReleasedTrialSummaryFactState,
  type ReleasedTrialSummarySourceKind,
  type ReleasedTrialSummaryWorkspace,
  type RetainReleasedTrialSummaryCommand,
  type ReviseReleasedTrialSummaryCommand,
  type SubmitTrialConclusionCommand,
} from "../api/trial-data-source";
import type { ControlledPrintDataSource } from "../api/controlled-print-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { FormalQualityLinkInspector } from "./formal-quality-link-inspector";
import type { FormalQualityLinkDataSource } from "../api/formal-quality-link-data-source";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import {
  DockedInspector,
  ObjectHeader,
  SectionAnchors,
} from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { ControlledPrintAction } from "../components/controlled-print-action";
import { AttachmentField } from "../components/field-attachment-primitives";
import {
  MobileEngineeringHandoff,
  ReviewedScanEntry,
} from "../components/mobile-field-actions";
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
type QualityState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; value: TrialQualityWorkspace }
  | { kind: "failed"; failure: RequestFailure };
type ReviewState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; value: TrialReviewWorkspace }
  | { kind: "failed"; failure: RequestFailure };
type ReleasedSummaryState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; value: ReleasedTrialSummaryWorkspace }
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

type QualityEditorKind =
  | "create_cavity"
  | "revise_cavity"
  | "create_defect"
  | "revise_defect"
  | "verify_defect";

interface QualityEditorState {
  kind: QualityEditorKind;
  sourceGlobalId: string | null;
  cavityGlobalId: string;
  characteristicKey: string;
  characteristicLabel: string;
  unit: string;
  nominalValue: string;
  lowerLimit: string;
  upperLimit: string;
  measurementState: "measured" | "not_measured";
  measuredValue: string;
  observedAt: string;
  evidenceGlobalId: string;
  evidenceSnapshotHash: string;
  businessCode: string;
  title: string;
  description: string;
  categoryKey: string;
  location: string;
  severity: TrialDefectSeverity;
  blocking: boolean;
  defectState: TrialDefectRevision["state"];
  rootCause: string;
  occurrenceCount: string;
  responsibleMemberGlobalId: string;
  responsibleMemberVersion: string;
  actionGlobalId: string;
  actionType: "containment" | "corrective" | "preventive";
  actionState: "planned" | "completed" | "verified";
  actionDetail: string;
  actionResponsibleMemberGlobalId: string;
  actionResponsibleMemberVersion: string;
  actionDueDate: string;
  verifierMemberGlobalId: string;
  verifierMemberVersion: string;
  verificationGlobalId: string;
  expectedAttemptSequence: string;
  verificationResult: "pass" | "fail";
  finding: string;
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

function countOpenBlockingDefects(
  workspace: TrialQualityWorkspace | null,
): number {
  if (!workspace) return 0;
  const latestByDefect = new Map<
    string,
    {
      readonly blocking: boolean;
      readonly state: string;
      readonly version: number;
    }
  >();
  for (const entry of workspace.defectRevisions) {
    const revision = entry.revision;
    const retained = latestByDefect.get(revision.defectGlobalId);
    if (!retained || revision.defectVersion > retained.version) {
      latestByDefect.set(revision.defectGlobalId, {
        blocking: revision.blocking,
        state: revision.state,
        version: revision.defectVersion,
      });
    }
  }
  return Array.from(latestByDefect.values()).filter(
    (revision) => revision.blocking && revision.state !== "closed",
  ).length;
}

function MobileTrialFieldSummary({
  execution,
  plan,
  projectId,
  quality,
  round,
}: {
  readonly execution: TrialExecutionWorkspace | null;
  readonly plan: TrialPlanDetail | null;
  readonly projectId: string;
  readonly quality: TrialQualityWorkspace | null;
  readonly round: TrialRoundSummary | null;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const nonCleanFiles =
    execution?.pendingFiles.filter((file) => file.scanState !== "clean")
      .length ?? 0;
  const evidenceActionAvailable = Boolean(
    sessionCommandContext && execution?.permissions.canManageEvidence,
  );
  const defectActionAvailable = Boolean(
    sessionCommandContext && execution && quality?.permissions.manageDefects,
  );

  return (
    <section
      aria-labelledby="mobile-trial-field-summary-title"
      className="mobile-trial-field-summary mobile-field-only"
      data-testid="mobile-trial-field-summary"
    >
      <div className="mobile-trial-field-summary__header">
        <h2 id="mobile-trial-field-summary-title">
          {t("Trial field summary")}
        </h2>
        <SemanticStatus
          label={
            round
              ? roundStateLabel(t, round.currentState)
              : t("No Round selected")
          }
          tone={round ? "info" : "warning"}
        />
      </div>
      <DefinitionList
        rows={[
          {
            label: t("Project stable ID"),
            value: projectId,
            exempt: "identifier",
          },
          {
            label: t("Trial Plan stable ID"),
            value: plan?.planGlobalId ?? t("Unavailable"),
            ...(plan ? { exempt: "identifier" as const } : {}),
          },
          {
            label: t("Plan version"),
            value: plan
              ? formatNumber(locale, plan.latestRevision.planVersion, 0)
              : t("Unavailable"),
          },
          {
            label: t("Selected Round"),
            value: round?.displayLabel ?? t("Not selected"),
            ...(round ? { exempt: "identifier" as const } : {}),
          },
          {
            label: t("Round version"),
            value: round
              ? formatNumber(locale, round.optimisticVersion, 0)
              : t("Unavailable"),
          },
          {
            label: t("Files not in clean state"),
            value: formatNumber(locale, nonCleanFiles, 0),
          },
          {
            label: t("Open blocking defects"),
            value: formatNumber(locale, countOpenBlockingDefects(quality), 0),
          },
          {
            label: t("Session command context"),
            value: sessionCommandContext ? t("Verified") : t("Unavailable"),
          },
          {
            label: t("Evidence photo action"),
            value: evidenceActionAvailable ? t("Available") : t("Unavailable"),
          },
          {
            label: t("Trial defect action"),
            value: defectActionAvailable ? t("Available") : t("Unavailable"),
          },
        ]}
      />
    </section>
  );
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

function defectStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: TrialDefectRevision["state"],
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
  }
}

function reviewReferenceKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: TrialReviewReferenceKind,
): string {
  switch (kind) {
    case "controlled_quality_report":
      return t("Controlled quality report");
    case "internal_sample_review":
      return t("Internal sample review");
    case "customer_evidence":
      return t("Customer evidence");
    case "deviation_or_waiver":
      return t("Deviation or waiver");
  }
}

function conclusionCodeLabel(
  t: ReturnType<typeof useI18n>["t"],
  code: TrialConclusionCode,
): string {
  switch (code) {
    case "pass":
      return t("Pass");
    case "conditional_pass":
      return t("Conditional pass");
    case "tooling_change":
      return t("Tooling change");
    case "design_change":
      return t("Design change");
    case "process_tuning":
      return t("Process tuning");
    case "material_change":
      return t("Material change");
    case "cancelled":
      return t("Cancelled");
  }
}

function conclusionStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: TrialConclusionRevision["state"],
): string {
  switch (state) {
    case "submitted":
      return t("Submitted");
    case "approved":
      return t("Approved");
    case "rejected":
      return t("Rejected");
    case "reopened":
      return t("Reopened");
  }
}

function reviewBlockerLabel(
  t: ReturnType<typeof useI18n>["t"],
  blocker: TrialConclusionBlocker["code"],
): string {
  switch (blocker) {
    case "missing_input_lock":
      return t("Input lock is missing");
    case "missing_actual":
      return t("Actual execution revision is missing");
    case "required_parameter_not_measured":
      return t("A required parameter is not measured");
    case "missing_cavity_result":
      return t("A required cavity result is missing");
    case "required_dimension_not_measured":
      return t("A required dimension is not measured");
    case "open_blocking_defect":
      return t("A blocking defect remains open");
    case "required_action_not_verified":
      return t("A required action is not independently verified");
    case "required_review_reference_unavailable":
      return t("A required review reference is unavailable");
    case "out_of_spec_blocking":
      return t("An out-of-spec result blocks this conclusion");
  }
}

function reviewResultStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state:
    | "measured"
    | "not_measured"
    | "unavailable"
    | "within_spec"
    | "out_of_spec",
): string {
  switch (state) {
    case "measured":
      return t("Measured");
    case "not_measured":
      return t("Not measured");
    case "unavailable":
      return t("Unavailable");
    case "within_spec":
      return t("Within specification");
    case "out_of_spec":
      return t("Out of specification");
  }
}

function qualityEditorLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: QualityEditorKind,
): string {
  switch (kind) {
    case "create_cavity":
      return t("Record cavity result");
    case "revise_cavity":
      return t("Append cavity result revision");
    case "create_defect":
      return t("Record Trial defect");
    case "revise_defect":
      return t("Append Trial defect revision");
    case "verify_defect":
      return t("Record independent verification");
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
    globalThis.queueMicrotask(() => {
      const matchMediaCandidate: unknown = Reflect.get(
        globalThis,
        "matchMedia",
      );
      const mobileViewport =
        typeof matchMediaCandidate === "function" &&
        (matchMediaCandidate as typeof globalThis.matchMedia).call(
          globalThis,
          "(width <= 920px)",
        ).matches;
      const mobilePhotoInput =
        kind === "upload" && mobileViewport
          ? document.getElementById("trial-evidence-photo")
          : null;
      (mobilePhotoInput ?? firstControl.current)?.focus();
    });
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
            <div className="desktop-engineering-only">
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
            </div>
            <div className="mobile-field-only">
              <AttachmentField
                accept="image/*"
                access={processing ? "read_only" : "editable"}
                capture="environment"
                guidance={t(
                  "Capture or choose one image. Selection remains local until you start the private upload.",
                )}
                id="trial-evidence-photo"
                label={t("Trial evidence photo")}
                onClearLocal={() => {
                  setSelectedFile(null);
                }}
                onSelectFile={(file) => {
                  setSelectedFile(file);
                }}
                onStart={uploadSelectedFile}
                state={
                  selectedFile
                    ? { kind: "local_selected", file: selectedFile }
                    : { kind: "empty" }
                }
              />
            </div>
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
                className="desktop-engineering-only"
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
      <Panel
        className="desktop-engineering-only"
        title={t("Locked preparation inputs")}
      >
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
      <Panel
        className="desktop-engineering-only"
        title={t("Actual process parameters")}
      >
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
      <Panel className="desktop-engineering-only" title={t("Sample Batches")}>
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

function initialQualityEditor(
  kind: QualityEditorKind,
  workspace: TrialQualityWorkspace,
  execution: TrialExecutionWorkspace | null,
  sourceGlobalId: string | null = null,
): QualityEditorState {
  const cavityResult = workspace.cavityResultRevisions.find(
    (revision) => revision.globalId === sourceGlobalId,
  );
  const defectEntry = workspace.defectRevisions.find(
    (entry) => entry.revision.globalId === sourceGlobalId,
  );
  const trialDefect =
    defectEntry?.source === "trial" ? defectEntry.revision : null;
  const sourceDefect = defectEntry?.revision ?? null;
  const sourceAction = sourceDefect?.actions[0] ?? null;
  const firstMeasurement = cavityResult?.measurements[0];
  const firstAction = trialDefect?.actions.find(
    (action) => action.state === "completed" || action.state === "verified",
  );
  const latestVerification = firstAction
    ? workspace.verificationRevisions
        .filter(
          (revision) =>
            revision.defectGlobalId === trialDefect?.defectGlobalId &&
            revision.actionGlobalId === firstAction.globalId,
        )
        .at(-1)
    : null;
  const evidence =
    cavityResult?.evidence[0] ??
    trialDefect?.evidence[0] ??
    workspace.cavityResultRevisions[0]?.evidence[0] ??
    workspace.defectRevisions.find((entry) => entry.source === "trial")
      ?.revision.evidence[0] ??
    null;
  const defaultCavity =
    sourceDefect?.cavityGlobalId ??
    workspace.cavityFilters[0]?.globalId ??
    execution?.inputLocks
      .at(-1)
      ?.references.find((reference) => reference.kind === "cavity")?.globalId ??
    "";
  return {
    actionGlobalId:
      kind === "verify_defect"
        ? (firstAction?.globalId ?? "")
        : (sourceAction?.globalId ?? ""),
    actionDetail: sourceAction?.detail ?? "",
    actionDueDate:
      sourceAction?.dueDate ?? new Date().toISOString().slice(0, 10),
    actionResponsibleMemberGlobalId:
      sourceAction?.responsibleMember.globalId ?? "",
    actionResponsibleMemberVersion: sourceAction
      ? String(sourceAction.responsibleMember.optimisticVersion)
      : "",
    actionState:
      defectEntry?.source === "tooling" && sourceAction?.state === "verified"
        ? "completed"
        : (sourceAction?.state ?? "planned"),
    actionType: sourceAction?.actionType ?? "corrective",
    blocking: sourceDefect?.blocking ?? false,
    businessCode: sourceDefect?.businessCode ?? "",
    categoryKey: sourceDefect?.categoryKey ?? "",
    cavityGlobalId: cavityResult?.cavityGlobalId ?? defaultCavity,
    characteristicKey: firstMeasurement?.characteristicKey ?? "",
    characteristicLabel: firstMeasurement?.label ?? "",
    description: sourceDefect?.description ?? "",
    defectState: trialDefect?.state ?? "open",
    evidenceGlobalId: evidence?.globalId ?? "",
    evidenceSnapshotHash: evidence?.snapshotHash ?? "",
    expectedAttemptSequence: latestVerification
      ? String(latestVerification.attemptSequence)
      : "",
    finding: "",
    kind,
    location: trialDefect?.location ?? "",
    lowerLimit: firstMeasurement?.lowerLimit ?? "",
    measuredValue: firstMeasurement?.value ?? "",
    measurementState: firstMeasurement?.state ?? "measured",
    nominalValue: firstMeasurement?.nominalValue ?? "",
    observedAt: utcInput(new Date().toISOString()),
    occurrenceCount: String(trialDefect?.occurrenceCount ?? 1),
    responsibleMemberGlobalId: trialDefect?.responsibleMember?.globalId ?? "",
    responsibleMemberVersion: trialDefect?.responsibleMember
      ? String(trialDefect.responsibleMember.optimisticVersion)
      : "",
    rootCause: trialDefect?.rootCause ?? "",
    severity: sourceDefect?.severity ?? "medium",
    sourceGlobalId,
    title: sourceDefect?.title ?? "",
    unit: firstMeasurement?.unit ?? "mm",
    upperLimit: firstMeasurement?.upperLimit ?? "",
    verificationGlobalId: latestVerification?.verificationGlobalId ?? "",
    verificationResult: "pass",
    verifierMemberGlobalId: latestVerification?.verifierMember.globalId ?? "",
    verifierMemberVersion: latestVerification
      ? String(latestVerification.verifierMember.optimisticVersion)
      : "",
  };
}

function TrialQualitySection({
  dataSource,
  execution,
  formalQualityDataSource,
  onWorkspace,
  projectId,
  reportWorkspaceDirty,
  workspace,
}: {
  dataSource: TrialDataSource;
  execution: TrialExecutionWorkspace | null;
  formalQualityDataSource?: FormalQualityLinkDataSource | undefined;
  onWorkspace: (value: TrialQualityWorkspace) => void;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  workspace: TrialQualityWorkspace;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [cavityFilter, setCavityFilter] = useState("");
  const [editor, setEditor] = useState<QualityEditorState | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const latestCommand = useRef<(() => void) | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const firstControl = useRef<HTMLInputElement | null>(null);
  const processing = command.kind === "processing";
  const lock = execution?.inputLocks.at(-1) ?? null;
  const sample = execution?.sampleBatchRevisions.at(-1) ?? null;
  const filteredCavityResults = workspace.cavityResultRevisions.filter(
    (revision) => !cavityFilter || revision.cavityGlobalId === cavityFilter,
  );
  const filteredDefects = workspace.defectRevisions.filter(
    (entry) => !cavityFilter || entry.revision.cavityGlobalId === cavityFilter,
  );
  const filteredPareto = workspace.pareto.filter(
    (row) => !cavityFilter || row.cavityGlobalId === cavityFilter,
  );
  const trialDefects = workspace.defectRevisions.filter(
    (
      entry,
    ): entry is Extract<TrialQualityDefectRevision, { source: "trial" }> =>
      entry.source === "trial",
  );
  const formalQualityDefect = trialDefects.at(-1)?.revision ?? null;

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!editor) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: editor.sourceGlobalId ?? workspace.trialRound.globalId,
      returnFocusTarget: () =>
        firstControl.current ??
        document.getElementById("trial-quality-primary-action"),
      version: `trial-quality-round-v${String(workspace.trialRound.optimisticVersion)}`,
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [editor, reportWorkspaceDirty, workspace.trialRound]);

  const closeEditor = (): void => {
    setEditor(null);
    setReviewOpen(false);
    setFormError(null);
    const target = returnFocus.current;
    globalThis.queueMicrotask(() => target?.focus());
  };

  const openEditor = (
    kind: QualityEditorKind,
    trigger: HTMLElement,
    sourceGlobalId: string | null = null,
  ): void => {
    returnFocus.current = trigger;
    setCommand({ kind: "idle" });
    setFormError(null);
    setReviewOpen(false);
    setEditor(initialQualityEditor(kind, workspace, execution, sourceGlobalId));
    globalThis.queueMicrotask(() => firstControl.current?.focus());
  };

  const evidenceValid = Boolean(
    editor &&
    uuidPattern.test(editor.evidenceGlobalId.trim()) &&
    /^[a-f0-9]{64}$/u.test(editor.evidenceSnapshotHash.trim()),
  );
  const actionPresent = Boolean(
    editor && (editor.actionGlobalId || editor.actionDetail.trim()),
  );
  const actionValid = Boolean(
    !actionPresent ||
    (editor &&
      Boolean(editor.actionDetail.trim()) &&
      uuidPattern.test(editor.actionResponsibleMemberGlobalId.trim()) &&
      Number.isInteger(Number(editor.actionResponsibleMemberVersion)) &&
      Number(editor.actionResponsibleMemberVersion) > 0 &&
      /^\d{4}-\d{2}-\d{2}$/u.test(editor.actionDueDate)),
  );
  const editorValid = Boolean(
    editor &&
    lock &&
    sample &&
    uuidPattern.test(editor.cavityGlobalId.trim()) &&
    evidenceValid &&
    (editor.kind === "create_cavity" || editor.kind === "revise_cavity"
      ? Boolean(editor.characteristicKey.trim()) &&
        Boolean(editor.characteristicLabel.trim()) &&
        Boolean(editor.unit.trim()) &&
        [editor.nominalValue, editor.lowerLimit, editor.upperLimit].every(
          (value) => Number.isFinite(Number(value)),
        ) &&
        Number(editor.lowerLimit) <= Number(editor.nominalValue) &&
        Number(editor.nominalValue) <= Number(editor.upperLimit) &&
        (editor.measurementState === "not_measured" ||
          Number.isFinite(Number(editor.measuredValue)))
      : editor.kind === "create_defect" || editor.kind === "revise_defect"
        ? Boolean(editor.businessCode.trim()) &&
          Boolean(editor.title.trim()) &&
          Boolean(editor.description.trim()) &&
          Boolean(editor.categoryKey.trim()) &&
          Boolean(editor.location.trim()) &&
          actionValid &&
          (editor.kind !== "create_defect" ||
            editor.sourceGlobalId !== null ||
            editor.defectState === "open") &&
          Number.isInteger(Number(editor.occurrenceCount)) &&
          Number(editor.occurrenceCount) > 0 &&
          (editor.defectState === "open" ||
            (uuidPattern.test(editor.responsibleMemberGlobalId.trim()) &&
              Number(editor.responsibleMemberVersion) > 0))
        : uuidPattern.test(editor.actionGlobalId.trim()) &&
          uuidPattern.test(editor.verifierMemberGlobalId.trim()) &&
          Number(editor.verifierMemberVersion) > 0 &&
          Boolean(editor.finding.trim()) &&
          Boolean(workspace.cavityResultRevisions[0])),
  );

  const reviewCommand = (): void => {
    if (!editorValid) {
      setFormError(
        t(
          "Complete every required quality field and exact evidence reference before review.",
        ),
      );
      return;
    }
    setFormError(null);
    setReviewOpen(true);
  };

  const runCommand = (
    label: string,
    operation: () => Promise<TrialQualityCommandResult>,
  ): void => {
    const execute = (): void => {
      setCommand({ kind: "processing", label });
      void operation()
        .then((result) => {
          onWorkspace(result.workspace);
          setEditor(null);
          setReviewOpen(false);
          setFormError(null);
          setCommand({ kind: "succeeded", label, replayed: result.replayed });
          const target = returnFocus.current;
          globalThis.queueMicrotask(() => target?.focus());
        })
        .catch((error: unknown) => {
          setReviewOpen(false);
          setCommand({ kind: "failed", failure: toRequestFailure(error) });
        });
    };
    latestCommand.current = execute;
    execute();
  };

  const confirmCommand = (reason: string): void => {
    if (!editor || !sessionCommandContext || !lock || !sample) return;
    const context = {
      csrfToken: sessionCommandContext.csrfToken,
      idempotencyKey: `trial-quality-${globalThis.crypto.randomUUID()}`,
      signal: new AbortController().signal,
    };
    const evidence = [
      {
        globalId: editor.evidenceGlobalId.trim(),
        snapshotHash: editor.evidenceSnapshotHash.trim(),
      },
    ];
    const measurement = {
      characteristicKey: editor.characteristicKey.trim(),
      label: editor.characteristicLabel.trim(),
      lowerLimit: editor.lowerLimit.trim(),
      nominalValue: editor.nominalValue.trim(),
      observedAt: utcInstant(editor.observedAt),
      required: true,
      source: "manual" as const,
      state: editor.measurementState,
      unit: editor.unit.trim(),
      upperLimit: editor.upperLimit.trim(),
      value:
        editor.measurementState === "measured"
          ? editor.measuredValue.trim()
          : null,
    };
    const round = workspace.trialRound;
    if (editor.kind === "create_cavity") {
      const commandValue: CreateTrialCavityResultCommand = {
        cavityGlobalId: editor.cavityGlobalId.trim(),
        evidence,
        expectedInputLockRevisionGlobalId: lock.globalId,
        expectedInputLockRevisionSnapshotHash: lock.snapshotHash,
        expectedRoundOptimisticVersion: round.optimisticVersion,
        expectedRoundSnapshotHash: round.snapshotHash,
        expectedSampleBatchRevisionSnapshotHash: sample.snapshotHash,
        measurements: [measurement],
        reason,
        sampleBatchRevisionGlobalId: sample.globalId,
      };
      runCommand(t("Recording cavity result"), () =>
        dataSource.createCavityResult(
          projectId,
          round.globalId,
          commandValue,
          context,
        ),
      );
      return;
    }
    if (editor.kind === "revise_cavity") {
      const revision = workspace.cavityResultRevisions.find(
        (candidate) => candidate.globalId === editor.sourceGlobalId,
      );
      if (!revision) return;
      const commandValue: ReviseTrialCavityResultCommand = {
        expectedInputLockRevisionGlobalId: lock.globalId,
        expectedInputLockRevisionSnapshotHash: lock.snapshotHash,
        expectedResultVersion: revision.resultVersion,
        expectedRevisionGlobalId: revision.globalId,
        expectedRevisionSnapshotHash: revision.snapshotHash,
        expectedRoundOptimisticVersion: round.optimisticVersion,
        expectedRoundSnapshotHash: round.snapshotHash,
        measurements: [
          measurement,
          ...revision.measurements.slice(1).map((value) => ({
            characteristicKey: value.characteristicKey,
            label: value.label,
            lowerLimit: value.lowerLimit,
            nominalValue: value.nominalValue,
            observedAt: value.observedAt,
            required: value.required,
            source: value.source,
            state: value.state,
            unit: value.unit,
            upperLimit: value.upperLimit,
            value: value.value,
          })),
        ],
        reason,
      };
      runCommand(t("Appending cavity result revision"), () =>
        dataSource.reviseCavityResult(
          projectId,
          round.globalId,
          revision.cavityResultGlobalId,
          commandValue,
          context,
        ),
      );
      return;
    }
    const member =
      editor.responsibleMemberGlobalId && editor.responsibleMemberVersion
        ? {
            globalId: editor.responsibleMemberGlobalId.trim(),
            optimisticVersion: Number(editor.responsibleMemberVersion),
          }
        : undefined;
    const sourceTrialDefect = trialDefects.find(
      (entry) => entry.revision.globalId === editor.sourceGlobalId,
    )?.revision;
    const existingAction = sourceTrialDefect?.actions.find(
      (action) => action.globalId === editor.actionGlobalId,
    );
    const editedAction = actionPresent
      ? {
          actionType: editor.actionType,
          detail: editor.actionDetail.trim(),
          dueDate: editor.actionDueDate,
          globalId: editor.actionGlobalId || null,
          responsibleMember: {
            globalId: editor.actionResponsibleMemberGlobalId.trim(),
            optimisticVersion: Number(editor.actionResponsibleMemberVersion),
          },
          state: editor.actionState,
          targetRoundGlobalId: round.globalId,
          targetRoundOptimisticVersion: round.optimisticVersion,
          targetRoundSnapshotHash: round.snapshotHash,
          verificationRevisionGlobalId:
            editor.actionState === "verified"
              ? (existingAction?.verificationRevisionGlobalId ?? null)
              : null,
          verificationRevisionSnapshotHash:
            editor.actionState === "verified"
              ? (existingAction?.verificationRevisionSnapshotHash ?? null)
              : null,
        }
      : null;
    if (editor.kind === "create_defect") {
      const predecessor = workspace.defectRevisions.find(
        (entry) =>
          entry.source === "tooling" &&
          entry.revision.globalId === editor.sourceGlobalId,
      );
      const commandValue: CreateTrialDefectCommand = {
        actions: editedAction ? [editedAction] : [],
        blocking: editor.blocking,
        businessCode: editor.businessCode.trim(),
        categoryKey: editor.categoryKey.trim(),
        cavityGlobalId: editor.cavityGlobalId.trim(),
        description: editor.description.trim(),
        evidence,
        expectedInputLockRevisionGlobalId: lock.globalId,
        expectedInputLockRevisionSnapshotHash: lock.snapshotHash,
        expectedRoundOptimisticVersion: round.optimisticVersion,
        expectedRoundSnapshotHash: round.snapshotHash,
        expectedSampleBatchRevisionSnapshotHash: sample.snapshotHash,
        location: editor.location.trim(),
        occurrenceCount: Number(editor.occurrenceCount),
        reason,
        rootCauseState: editor.rootCause.trim() ? "recorded" : "pending",
        sampleBatchRevisionGlobalId: sample.globalId,
        severity: editor.severity,
        state: editor.defectState,
        title: editor.title.trim(),
        ...(editor.rootCause.trim()
          ? { rootCause: editor.rootCause.trim() }
          : {}),
        ...(member ? { responsibleMember: member } : {}),
        ...(predecessor
          ? {
              defectGlobalId: predecessor.revision.defectGlobalId,
              expectedDefectVersion: predecessor.revision.defectVersion,
              expectedPredecessorGlobalId: predecessor.revision.globalId,
              expectedPredecessorKind: "tooling_defect_revision" as const,
              expectedPredecessorSnapshotHash:
                predecessor.revision.snapshotHash,
            }
          : {}),
      };
      runCommand(t("Recording Trial defect"), () =>
        dataSource.createDefect(
          projectId,
          round.globalId,
          commandValue,
          context,
        ),
      );
      return;
    }
    const defectEntry = trialDefects.find(
      (entry) => entry.revision.globalId === editor.sourceGlobalId,
    );
    if (!defectEntry) return;
    const defect = defectEntry.revision;
    if (editor.kind === "revise_defect") {
      const commandValue: ReviseTrialDefectCommand = {
        actions: [
          ...(editedAction ? [editedAction] : []),
          ...defect.actions
            .filter((action) => action.globalId !== editor.actionGlobalId)
            .map((action) => ({
              actionType: action.actionType,
              detail: action.detail,
              dueDate: action.dueDate,
              globalId: action.globalId,
              responsibleMember: {
                globalId: action.responsibleMember.globalId,
                optimisticVersion: action.responsibleMember.optimisticVersion,
              },
              state: action.state,
              targetRoundGlobalId: action.targetRoundGlobalId,
              targetRoundOptimisticVersion: action.targetRoundOptimisticVersion,
              targetRoundSnapshotHash: action.targetRoundSnapshotHash,
              verificationRevisionGlobalId: action.verificationRevisionGlobalId,
              verificationRevisionSnapshotHash:
                action.verificationRevisionSnapshotHash,
            })),
        ],
        blocking: editor.blocking,
        businessCode: editor.businessCode.trim(),
        categoryKey: editor.categoryKey.trim(),
        cavityGlobalId: editor.cavityGlobalId.trim(),
        description: editor.description.trim(),
        evidence,
        expectedDefectVersion: defect.defectVersion,
        expectedInputLockRevisionGlobalId: lock.globalId,
        expectedInputLockRevisionSnapshotHash: lock.snapshotHash,
        expectedPredecessorGlobalId: defect.globalId,
        expectedPredecessorKind: "trial_defect_revision",
        expectedPredecessorSnapshotHash: defect.snapshotHash,
        expectedRoundOptimisticVersion: round.optimisticVersion,
        expectedRoundSnapshotHash: round.snapshotHash,
        expectedSampleBatchRevisionSnapshotHash: sample.snapshotHash,
        location: editor.location.trim(),
        occurrenceCount: Number(editor.occurrenceCount),
        reason,
        rootCauseState: editor.rootCause.trim() ? "recorded" : "pending",
        sampleBatchRevisionGlobalId: sample.globalId,
        severity: editor.severity,
        state: editor.defectState,
        title: editor.title.trim(),
        ...(editor.rootCause.trim()
          ? { rootCause: editor.rootCause.trim() }
          : {}),
        ...(member ? { responsibleMember: member } : {}),
      };
      runCommand(t("Appending Trial defect revision"), () =>
        dataSource.reviseDefect(
          projectId,
          round.globalId,
          defect.defectGlobalId,
          commandValue,
          context,
        ),
      );
      return;
    }
    const cavityResult = workspace.cavityResultRevisions[0];
    if (!cavityResult) return;
    const commandValue: VerifyTrialDefectCommand = {
      actionGlobalId: editor.actionGlobalId.trim(),
      cavityResultRevisionGlobalId: cavityResult.globalId,
      evidence,
      expectedCavityResultRevisionSnapshotHash: cavityResult.snapshotHash,
      expectedDefectRevisionGlobalId: defect.globalId,
      expectedDefectRevisionSnapshotHash: defect.snapshotHash,
      expectedTargetRoundOptimisticVersion: round.optimisticVersion,
      expectedTargetRoundSnapshotHash: round.snapshotHash,
      finding: editor.finding.trim(),
      observedAt: utcInstant(editor.observedAt),
      result: editor.verificationResult,
      targetRoundGlobalId: round.globalId,
      verifierMember: {
        globalId: editor.verifierMemberGlobalId.trim(),
        optimisticVersion: Number(editor.verifierMemberVersion),
      },
      ...(editor.verificationGlobalId && editor.expectedAttemptSequence
        ? {
            expectedAttemptSequence: Number(editor.expectedAttemptSequence),
            verificationGlobalId: editor.verificationGlobalId,
          }
        : {}),
    };
    runCommand(t("Recording independent verification"), () =>
      dataSource.verifyDefect(
        projectId,
        round.globalId,
        defect.defectGlobalId,
        commandValue,
        context,
      ),
    );
  };

  return (
    <>
      <Panel title={t("Trial quality workspace")}>
        <div className="mobile-field-only">
          <ReviewedScanEntry
            disabled={!workspace.permissions.view || processing}
            onApply={(reference) => {
              setCavityFilter(reference.value);
              setEditor((current) =>
                current
                  ? { ...current, cavityGlobalId: reference.value }
                  : current,
              );
            }}
            references={workspace.cavityFilters.map((cavity) => ({
              label: cavity.globalId,
              value: cavity.globalId,
            }))}
          />
        </div>
        <div className="trial-live__command-bar">
          {workspace.permissions.recordCavityResult ? (
            <Button
              disabled={!sessionCommandContext || !execution || processing}
              id="trial-quality-primary-action"
              onClick={(event) => {
                openEditor("create_cavity", event.currentTarget);
              }}
              visual="primary"
            >
              {t("Record cavity result")}
            </Button>
          ) : null}
          {workspace.permissions.manageDefects ? (
            <Button
              disabled={!sessionCommandContext || !execution || processing}
              onClick={(event) => {
                openEditor("create_defect", event.currentTarget);
              }}
            >
              {t("Record Trial defect")}
            </Button>
          ) : null}
          <label className="trial-live__filter">
            <span>{t("Cavity filter")}</span>
            <Select
              onChange={(event) => {
                setCavityFilter(event.target.value);
              }}
              value={cavityFilter}
            >
              <option value="">{t("All cavities")}</option>
              {workspace.cavityFilters.map((cavity) => (
                <option key={cavity.globalId} value={cavity.globalId}>
                  {cavity.globalId}
                </option>
              ))}
            </Select>
          </label>
        </div>
        <DefinitionList
          rows={[
            {
              label: t("Cavity result revisions"),
              value: formatNumber(locale, filteredCavityResults.length, 0),
            },
            {
              label: t("Defect timeline revisions"),
              value: formatNumber(locale, filteredDefects.length, 0),
            },
            {
              label: t("Independent verification attempts"),
              value: formatNumber(
                locale,
                workspace.verificationRevisions.length,
                0,
              ),
            },
          ]}
        />
      </Panel>
      {!sessionCommandContext ||
      !workspace.permissions.view ||
      (!workspace.permissions.recordCavityResult &&
        !workspace.permissions.manageDefects &&
        !workspace.permissions.verifyDefects) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Trial quality is read only in this session.")}</span>
          <span>
            {t(
              "The server still controls Project membership and every quality command permission.",
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
              "The exact quality command is being verified and committed atomically.",
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
                  "The exact prior quality command response was replayed safely.",
                )
              : t("The quality command completed with immutable audit truth.")}
          </span>
        </div>
      ) : null}
      {command.kind === "failed" ? (
        <Panel title={t("Trial quality command not completed")}>
          <RequestFailurePanel failure={command.failure} />
          {canRetry(command.failure) ? (
            <Button onClick={() => latestCommand.current?.()}>
              {t("Retry exact command")}
            </Button>
          ) : null}
        </Panel>
      ) : null}
      {editor ? (
        <Panel title={qualityEditorLabel(t, editor.kind)}>
          <form
            className="trial-live__quality-form"
            onSubmit={(event) => {
              event.preventDefault();
              reviewCommand();
            }}
          >
            {(editor.kind === "create_cavity" ||
              editor.kind === "revise_cavity") && (
              <>
                <label>
                  <span>{t("Cavity stable ID")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        cavityGlobalId: event.target.value,
                      });
                    }}
                    ref={firstControl}
                    value={editor.cavityGlobalId}
                  />
                </label>
                <label>
                  <span>{t("Characteristic key")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        characteristicKey: event.target.value,
                      });
                    }}
                    value={editor.characteristicKey}
                  />
                </label>
                <label>
                  <span>{t("Characteristic label")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        characteristicLabel: event.target.value,
                      });
                    }}
                    value={editor.characteristicLabel}
                  />
                </label>
                <label>
                  <span>{t("Unit")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({ ...editor, unit: event.target.value });
                    }}
                    value={editor.unit}
                  />
                </label>
                <label>
                  <span>{t("Lower limit")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({ ...editor, lowerLimit: event.target.value });
                    }}
                    value={editor.lowerLimit}
                  />
                </label>
                <label>
                  <span>{t("Nominal value")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        nominalValue: event.target.value,
                      });
                    }}
                    value={editor.nominalValue}
                  />
                </label>
                <label>
                  <span>{t("Upper limit")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({ ...editor, upperLimit: event.target.value });
                    }}
                    value={editor.upperLimit}
                  />
                </label>
                <label>
                  <span>{t("Measurement state")}</span>
                  <Select
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        measurementState: event.target.value as
                          | "measured"
                          | "not_measured",
                      });
                    }}
                    value={editor.measurementState}
                  >
                    <option value="measured">{t("Measured")}</option>
                    <option value="not_measured">{t("Not measured")}</option>
                  </Select>
                </label>
                <label>
                  <span>{t("Measured value")}</span>
                  <TextInput
                    disabled={editor.measurementState === "not_measured"}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        measuredValue: event.target.value,
                      });
                    }}
                    value={editor.measuredValue}
                  />
                </label>
              </>
            )}
            {(editor.kind === "create_defect" ||
              editor.kind === "revise_defect") && (
              <>
                <label>
                  <span>{t("Cavity stable ID")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        cavityGlobalId: event.target.value,
                      });
                    }}
                    ref={firstControl}
                    value={editor.cavityGlobalId}
                  />
                </label>
                <label>
                  <span>{t("Defect code")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        businessCode: event.target.value,
                      });
                    }}
                    value={editor.businessCode}
                  />
                </label>
                <label>
                  <span>{t("Title")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({ ...editor, title: event.target.value });
                    }}
                    value={editor.title}
                  />
                </label>
                <label>
                  <span>{t("Category key")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({ ...editor, categoryKey: event.target.value });
                    }}
                    value={editor.categoryKey}
                  />
                </label>
                <label>
                  <span>{t("Location")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({ ...editor, location: event.target.value });
                    }}
                    value={editor.location}
                  />
                </label>
                <label>
                  <span>{t("Severity")}</span>
                  <Select
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        severity: event.target.value as TrialDefectSeverity,
                      });
                    }}
                    value={editor.severity}
                  >
                    {(["low", "medium", "high", "critical"] as const).map(
                      (severity) => (
                        <option key={severity} value={severity}>
                          {severityLabel(t, severity)}
                        </option>
                      ),
                    )}
                  </Select>
                </label>
                <label>
                  <span>{t("Defect state")}</span>
                  <Select
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        defectState: event.target
                          .value as TrialDefectRevision["state"],
                      });
                    }}
                    value={editor.defectState}
                  >
                    {(
                      [
                        "open",
                        "assigned",
                        "in_progress",
                        "ready_for_verification",
                        "closed",
                        "reopened",
                      ] as const
                    ).map((state) => (
                      <option key={state} value={state}>
                        {defectStateLabel(t, state)}
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("Occurrence count")}</span>
                  <TextInput
                    min={1}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        occurrenceCount: event.target.value,
                      });
                    }}
                    type="number"
                    value={editor.occurrenceCount}
                  />
                </label>
                <label className="trial-live__editor-wide">
                  <span>{t("Description")}</span>
                  <textarea
                    onChange={(event) => {
                      setEditor({ ...editor, description: event.target.value });
                    }}
                    value={editor.description}
                  />
                </label>
                <label className="trial-live__editor-wide">
                  <span>{t("Root cause")}</span>
                  <textarea
                    onChange={(event) => {
                      setEditor({ ...editor, rootCause: event.target.value });
                    }}
                    value={editor.rootCause}
                  />
                </label>
                <label>
                  <span>{t("Responsible member stable ID")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        responsibleMemberGlobalId: event.target.value,
                      });
                    }}
                    value={editor.responsibleMemberGlobalId}
                  />
                </label>
                <label>
                  <span>{t("Responsible member version")}</span>
                  <TextInput
                    min={1}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        responsibleMemberVersion: event.target.value,
                      });
                    }}
                    type="number"
                    value={editor.responsibleMemberVersion}
                  />
                </label>
                <fieldset className="trial-live__quality-action trial-live__editor-wide">
                  <legend>{t("Governed defect action")}</legend>
                  <label className="trial-live__editor-wide">
                    <span>{t("Action detail")}</span>
                    <textarea
                      onChange={(event) => {
                        setEditor({
                          ...editor,
                          actionDetail: event.target.value,
                        });
                      }}
                      value={editor.actionDetail}
                    />
                  </label>
                  <label>
                    <span>{t("Action type")}</span>
                    <Select
                      onChange={(event) => {
                        setEditor({
                          ...editor,
                          actionType: event.target.value as
                            | "containment"
                            | "corrective"
                            | "preventive",
                        });
                      }}
                      value={editor.actionType}
                    >
                      <option value="containment">{t("Containment")}</option>
                      <option value="corrective">{t("Corrective")}</option>
                      <option value="preventive">{t("Preventive")}</option>
                    </Select>
                  </label>
                  <label>
                    <span>{t("Action state")}</span>
                    <Select
                      onChange={(event) => {
                        setEditor({
                          ...editor,
                          actionState: event.target.value as
                            | "planned"
                            | "completed"
                            | "verified",
                        });
                      }}
                      value={editor.actionState}
                    >
                      <option value="planned">{t("Planned")}</option>
                      <option value="completed">{t("Completed")}</option>
                      {editor.actionState === "verified" ? (
                        <option value="verified">{t("Verified")}</option>
                      ) : null}
                    </Select>
                  </label>
                  <label>
                    <span>{t("Action responsible member stable ID")}</span>
                    <TextInput
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
                    <span>{t("Action responsible member version")}</span>
                    <TextInput
                      min={1}
                      onChange={(event) => {
                        setEditor({
                          ...editor,
                          actionResponsibleMemberVersion: event.target.value,
                        });
                      }}
                      type="number"
                      value={editor.actionResponsibleMemberVersion}
                    />
                  </label>
                  <label>
                    <span>{t("Due date")}</span>
                    <TextInput
                      onChange={(event) => {
                        setEditor({
                          ...editor,
                          actionDueDate: event.target.value,
                        });
                      }}
                      type="date"
                      value={editor.actionDueDate}
                    />
                  </label>
                  <p className="context-help trial-live__editor-wide">
                    {t(
                      "Leave the action detail empty only when this defect revision has no governed action.",
                    )}
                  </p>
                </fieldset>
                <label className="checkbox-field">
                  <input
                    checked={editor.blocking}
                    onChange={(event) => {
                      setEditor({ ...editor, blocking: event.target.checked });
                    }}
                    type="checkbox"
                  />
                  <span>{t("Blocking defect")}</span>
                </label>
              </>
            )}
            {editor.kind === "verify_defect" ? (
              <>
                <label>
                  <span>{t("Action stable ID")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        actionGlobalId: event.target.value,
                      });
                    }}
                    ref={firstControl}
                    value={editor.actionGlobalId}
                  />
                </label>
                <label>
                  <span>{t("Verification result")}</span>
                  <Select
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        verificationResult: event.target.value as
                          | "pass"
                          | "fail",
                      });
                    }}
                    value={editor.verificationResult}
                  >
                    <option value="pass">{t("Pass")}</option>
                    <option value="fail">{t("Fail")}</option>
                  </Select>
                </label>
                <label>
                  <span>{t("Verifier member stable ID")}</span>
                  <TextInput
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        verifierMemberGlobalId: event.target.value,
                      });
                    }}
                    value={editor.verifierMemberGlobalId}
                  />
                </label>
                <label>
                  <span>{t("Verifier member version")}</span>
                  <TextInput
                    min={1}
                    onChange={(event) => {
                      setEditor({
                        ...editor,
                        verifierMemberVersion: event.target.value,
                      });
                    }}
                    type="number"
                    value={editor.verifierMemberVersion}
                  />
                </label>
                <label className="trial-live__editor-wide">
                  <span>{t("Verification finding")}</span>
                  <textarea
                    onChange={(event) => {
                      setEditor({ ...editor, finding: event.target.value });
                    }}
                    value={editor.finding}
                  />
                </label>
              </>
            ) : null}
            {(editor.kind === "create_cavity" ||
              editor.kind === "revise_cavity" ||
              editor.kind === "verify_defect") && (
              <label>
                <span>{t("Observed at")}</span>
                <TextInput
                  onChange={(event) => {
                    setEditor({ ...editor, observedAt: event.target.value });
                  }}
                  type="datetime-local"
                  value={editor.observedAt}
                />
              </label>
            )}
            <label>
              <span>{t("Evidence stable ID")}</span>
              <TextInput
                onChange={(event) => {
                  setEditor({
                    ...editor,
                    evidenceGlobalId: event.target.value,
                  });
                }}
                value={editor.evidenceGlobalId}
              />
            </label>
            <label className="trial-live__editor-wide">
              <span>{t("Evidence snapshot")}</span>
              <TextInput
                onChange={(event) => {
                  setEditor({
                    ...editor,
                    evidenceSnapshotHash: event.target.value,
                  });
                }}
                value={editor.evidenceSnapshotHash}
              />
            </label>
            {formError ? (
              <p className="form-error trial-live__editor-wide" role="alert">
                {formError}
              </p>
            ) : null}
            <p className="context-help trial-live__editor-wide">
              {t(
                "The server rechecks every predecessor, Round, input lock, Sample Batch, evidence and member version before append.",
              )}
            </p>
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
      <Panel className="desktop-engineering-only" title={t("Defect Pareto")}>
        {filteredPareto.length ? (
          <table
            aria-label={t("Defect Pareto")}
            className="data-table"
            tabIndex={0}
          >
            <thead>
              <tr>
                <th>{t("Category")}</th>
                <th>{t("Cavity")}</th>
                <th>{t("Severity")}</th>
                <th>{t("Occurrences")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredPareto.map((row) => (
                <tr
                  key={`${row.categoryKey}-${row.cavityGlobalId}-${row.severity}`}
                >
                  <td data-language-exempt="identifier">{row.categoryKey}</td>
                  <td data-language-exempt="identifier">
                    {row.cavityGlobalId}
                  </td>
                  <td>
                    <SemanticStatus
                      label={severityLabel(t, row.severity)}
                      tone="warning"
                    />
                  </td>
                  <td>{formatNumber(locale, row.count, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state" role="status">
            <strong>{t("No defects match the selected cavity.")}</strong>
            <span>
              {t(
                "The Pareto uses immutable defect occurrence counts, not revision row counts.",
              )}
            </span>
          </div>
        )}
      </Panel>
      <Panel
        className="desktop-engineering-only"
        title={t("Cavity measurements")}
      >
        {filteredCavityResults.length ? (
          <table
            aria-label={t("Cavity measurements")}
            className="data-table"
            tabIndex={0}
          >
            <thead>
              <tr>
                <th>{t("Cavity")}</th>
                <th>{t("Version")}</th>
                <th>{t("Characteristic")}</th>
                <th>{t("Specification")}</th>
                <th>{t("Measured value")}</th>
                <th>{t("Comparison")}</th>
                <th>{t("Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredCavityResults.flatMap((revision) =>
                revision.measurements.map((measurement, index) => (
                  <tr
                    key={`${revision.globalId}-${measurement.characteristicKey}`}
                  >
                    <td data-language-exempt="identifier">
                      {revision.cavityGlobalId}
                    </td>
                    <td>{formatNumber(locale, revision.resultVersion, 0)}</td>
                    <td data-language-exempt="business-data">
                      {measurement.label}
                    </td>
                    <td data-language-exempt="business-data">
                      {measurement.lowerLimit}–{measurement.nominalValue}–
                      {measurement.upperLimit} {measurement.unit}
                    </td>
                    <td data-language-exempt="business-data">
                      {measurement.value ?? "—"}
                    </td>
                    <td>
                      <SemanticStatus
                        label={
                          measurement.comparisonState === "within_spec"
                            ? t("Within specification")
                            : measurement.comparisonState === "out_of_spec"
                              ? t("Out of specification")
                              : t("Not measured")
                        }
                        tone={
                          measurement.comparisonState === "within_spec"
                            ? "success"
                            : "warning"
                        }
                      />
                    </td>
                    <td>
                      {index === 0 &&
                      workspace.permissions.recordCavityResult ? (
                        <Button
                          onClick={(event) => {
                            openEditor(
                              "revise_cavity",
                              event.currentTarget,
                              revision.globalId,
                            );
                          }}
                        >
                          {t("Revise")}
                        </Button>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        ) : (
          <div className="empty-state" role="status">
            <strong>{t("No cavity result has been recorded.")}</strong>
            <span>
              {t(
                "Record exact measurements against one Sample Batch revision and clean evidence snapshot.",
              )}
            </span>
          </div>
        )}
      </Panel>
      <Panel className="desktop-engineering-only" title={t("Defect timeline")}>
        {filteredDefects.length ? (
          <table
            aria-label={t("Defect timeline")}
            className="data-table"
            tabIndex={0}
          >
            <thead>
              <tr>
                <th>{t("Source")}</th>
                <th>{t("Defect")}</th>
                <th>{t("Cavity")}</th>
                <th>{t("Severity")}</th>
                <th>{t("State")}</th>
                <th>{t("Occurrences")}</th>
                <th>{t("Version")}</th>
                <th>{t("Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredDefects.map((entry) => (
                <tr key={entry.revision.globalId}>
                  <td>
                    {entry.source === "tooling" ? t("Tooling") : t("Trial")}
                  </td>
                  <td>
                    <strong data-language-exempt="identifier">
                      {entry.revision.businessCode}
                    </strong>
                    <br />
                    <span data-language-exempt="business-data">
                      {entry.revision.title}
                    </span>
                  </td>
                  <td data-language-exempt="identifier">
                    {entry.revision.cavityGlobalId ?? "—"}
                  </td>
                  <td>
                    <SemanticStatus
                      label={severityLabel(t, entry.revision.severity)}
                      tone="warning"
                    />
                  </td>
                  <td>{defectStateLabel(t, entry.revision.state)}</td>
                  <td>
                    {entry.source === "trial"
                      ? formatNumber(locale, entry.revision.occurrenceCount, 0)
                      : "—"}
                  </td>
                  <td>
                    {formatNumber(locale, entry.revision.defectVersion, 0)}
                  </td>
                  <td className="trial-live__row-actions">
                    {entry.source === "tooling" &&
                    workspace.permissions.manageDefects ? (
                      <Button
                        onClick={(event) => {
                          openEditor(
                            "create_defect",
                            event.currentTarget,
                            entry.revision.globalId,
                          );
                        }}
                      >
                        {t("Continue in Trial")}
                      </Button>
                    ) : null}
                    {entry.source === "trial" &&
                    workspace.permissions.manageDefects ? (
                      <Button
                        onClick={(event) => {
                          openEditor(
                            "revise_defect",
                            event.currentTarget,
                            entry.revision.globalId,
                          );
                        }}
                      >
                        {t("Revise")}
                      </Button>
                    ) : null}
                    {entry.source === "trial" &&
                    workspace.permissions.verifyDefects &&
                    entry.revision.actions.some(
                      (action) =>
                        action.state === "completed" ||
                        action.state === "verified",
                    ) ? (
                      <Button
                        onClick={(event) => {
                          openEditor(
                            "verify_defect",
                            event.currentTarget,
                            entry.revision.globalId,
                          );
                        }}
                      >
                        {t("Verify")}
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state" role="status">
            <strong>{t("No defects match the selected cavity.")}</strong>
            <span>
              {t(
                "Tooling and Trial revisions share one stable defect identity without rewriting history.",
              )}
            </span>
          </div>
        )}
      </Panel>
      <Panel className="desktop-engineering-only" title={t("Defect actions")}>
        {trialDefects.some((entry) => entry.revision.actions.length) ? (
          <table
            aria-label={t("Defect actions")}
            className="data-table"
            tabIndex={0}
          >
            <thead>
              <tr>
                <th>{t("Defect")}</th>
                <th>{t("Action type")}</th>
                <th>{t("Action")}</th>
                <th>{t("Responsible member")}</th>
                <th>{t("Due date")}</th>
                <th>{t("Target Round")}</th>
                <th>{t("State")}</th>
              </tr>
            </thead>
            <tbody>
              {trialDefects.flatMap((entry) =>
                entry.revision.actions.map((action) => (
                  <tr key={action.globalId}>
                    <td data-language-exempt="identifier">
                      {entry.revision.businessCode}
                    </td>
                    <td>
                      {action.actionType === "containment"
                        ? t("Containment")
                        : action.actionType === "corrective"
                          ? t("Corrective")
                          : t("Preventive")}
                    </td>
                    <td data-language-exempt="business-data">
                      {action.detail}
                    </td>
                    <td data-language-exempt="identifier">
                      {action.responsibleMember.userId}
                    </td>
                    <td>{action.dueDate}</td>
                    <td data-language-exempt="identifier">
                      {action.targetRoundGlobalId}
                    </td>
                    <td>
                      {action.state === "planned"
                        ? t("Planned")
                        : action.state === "completed"
                          ? t("Completed")
                          : t("Verified")}
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        ) : (
          <div className="empty-state" role="status">
            <strong>{t("No governed defect action is recorded.")}</strong>
            <span>
              {t(
                "Actions remain part of immutable defect revisions and target an exact Trial Round snapshot.",
              )}
            </span>
          </div>
        )}
      </Panel>
      {formalQualityDefect ? (
        <FormalQualityLinkInspector
          dataSource={formalQualityDataSource}
          projectId={projectId}
          source={{
            scopeGlobalId: workspace.trialRound.globalId,
            scopeKind: "trial_round",
            sourceCapability: workspace.permissions.manageDefects,
            sourceGlobalId: formalQualityDefect.defectGlobalId,
            sourceKind: "trial_defect",
            sourceSnapshotHash: formalQualityDefect.snapshotHash,
            sourceVersion: formalQualityDefect.defectVersion,
          }}
        />
      ) : null}
      <Panel
        className="desktop-engineering-only"
        title={t("Independent verification")}
      >
        {workspace.verificationRevisions.length ? (
          <table
            aria-label={t("Independent verification")}
            className="data-table"
            tabIndex={0}
          >
            <thead>
              <tr>
                <th>{t("Attempt")}</th>
                <th>{t("Defect")}</th>
                <th>{t("Action")}</th>
                <th>{t("Verification Round")}</th>
                <th>{t("Verifier")}</th>
                <th>{t("Result")}</th>
                <th>{t("Finding")}</th>
                <th>{t("Observed at")}</th>
              </tr>
            </thead>
            <tbody>
              {workspace.verificationRevisions.map((revision) => (
                <tr key={revision.globalId}>
                  <td>{formatNumber(locale, revision.attemptSequence, 0)}</td>
                  <td data-language-exempt="identifier">
                    {revision.defectGlobalId}
                  </td>
                  <td data-language-exempt="identifier">
                    {revision.actionGlobalId}
                  </td>
                  <td data-language-exempt="identifier">
                    {revision.verificationRoundGlobalId}
                  </td>
                  <td data-language-exempt="identifier">
                    {revision.verifierMember.userId}
                  </td>
                  <td>
                    <SemanticStatus
                      label={revision.result === "pass" ? t("Pass") : t("Fail")}
                      tone={revision.result === "pass" ? "success" : "warning"}
                    />
                  </td>
                  <td data-language-exempt="business-data">
                    {revision.finding}
                  </td>
                  <td>{formatDateTime(locale, revision.observedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state" role="status">
            <strong>
              {t("No independent verification has been recorded.")}
            </strong>
            <span>
              {t(
                "Verification must bind one completed action, target Round and cavity result revision exactly.",
              )}
            </span>
          </div>
        )}
      </Panel>
      <Panel title={t("External quality effects")}>
        <div className="trial-live__external-effects">
          {[
            t("NCR creation"),
            t("Formal quality inspection"),
            t("Gate effect"),
            t("Tooling lifecycle effect"),
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
        <p className="context-help">
          {t(
            "No external NCR, formal Quality Inspection, Gate decision or Tooling lifecycle state is created by this workspace.",
          )}
        </p>
      </Panel>
      {reviewOpen && editor ? (
        <ImpactReview
          confirmLabel={qualityEditorLabel(t, editor.kind)}
          details={{
            objectIdentity:
              editor.sourceGlobalId ?? workspace.trialRound.globalId,
            version: `v${String(workspace.trialRound.optimisticVersion)}`,
            impact: t(
              "Appends immutable cavity, defect or verification quality history without overwriting prior evidence.",
            ),
            permission: t(
              "The server rechecks Project membership, quality role and current Round-state authority.",
            ),
            irreversible: t(
              "Committed quality history cannot be edited or deleted through generic CRUD.",
            ),
            failureHandling: t(
              "A failed command changes no quality row and can be retried with the same exact request.",
            ),
            audit: t(
              "The command records actor, request, trace, reason and exact predecessor snapshots.",
            ),
          }}
          onCancel={() => {
            setReviewOpen(false);
          }}
          onConfirm={confirmCommand}
          reasonMaxLength={1000}
          returnFocusTarget={() => returnFocus.current}
          title={t("Review immutable Trial quality command")}
        />
      ) : null}
    </>
  );
}

type ReviewCommandKind =
  | "begin_analysis"
  | "create_comparison"
  | "create_reference"
  | "submit_conclusion"
  | "decide_conclusion"
  | "reopen_conclusion";

interface ReviewDraft {
  conclusionCode: TrialConclusionCode;
  decision: "approved" | "rejected";
  fileRevisionGlobalId: string;
  fileRevisionSnapshotHash: string;
  partRevisionGlobalId: string;
  partRevisionSnapshotHash: string;
  proposedGateEffect: string;
  proposedNextWork: string;
  proposedNpiEffect: string;
  referenceKind: TrialReviewReferenceKind;
  toolingRevisionGlobalId: string;
  toolingRevisionSnapshotHash: string;
  toolingSetGlobalId: string;
  toolingSetSnapshotHash: string;
}

function latestReviewReferences(
  workspace: TrialReviewWorkspace,
): TrialReviewWorkspace["reviewReferenceRevisions"] {
  const latest = new Map<
    string,
    TrialReviewWorkspace["reviewReferenceRevisions"][number]
  >();
  for (const revision of workspace.reviewReferenceRevisions) {
    const current = latest.get(revision.referenceGlobalId);
    if (!current || revision.referenceVersion > current.referenceVersion)
      latest.set(revision.referenceGlobalId, revision);
  }
  return [...latest.values()];
}

function reviewCommandLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: ReviewCommandKind,
): string {
  switch (kind) {
    case "begin_analysis":
      return t("Begin analysis");
    case "create_comparison":
      return t("Create exact comparison");
    case "create_reference":
      return t("Bind review reference");
    case "submit_conclusion":
      return t("Submit conclusion proposal");
    case "decide_conclusion":
      return t("Record conclusion decision");
    case "reopen_conclusion":
      return t("Reopen conclusion");
  }
}

function TrialReviewSection({
  candidateRounds,
  dataSource,
  onWorkspace,
  projectId,
  reportWorkspaceDirty,
  workspace,
}: {
  candidateRounds: readonly TrialRoundSummary[];
  dataSource: TrialDataSource;
  onWorkspace: (value: TrialReviewWorkspace) => void;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  workspace: TrialReviewWorkspace;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const latestPolicy = workspace.policyVersions.at(-1) ?? null;
  const latestComparison = workspace.comparisonSnapshots.at(-1) ?? null;
  const references = latestReviewReferences(workspace);
  const latestConclusion = workspace.conclusionRevisions.at(-1) ?? null;
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const [reviewOpen, setReviewOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [draftDirty, setDraftDirty] = useState(false);
  const [draft, setDraft] = useState<ReviewDraft>({
    conclusionCode:
      latestPolicy?.allowedConclusionCodes[0] ?? trialConclusionCodes[0],
    decision: "approved",
    fileRevisionGlobalId: "",
    fileRevisionSnapshotHash: "",
    partRevisionGlobalId: "",
    partRevisionSnapshotHash: "",
    proposedGateEffect: "",
    proposedNextWork: "",
    proposedNpiEffect: "",
    referenceKind:
      latestPolicy?.requiredReferenceKinds[0] ?? trialReviewReferenceKinds[0],
    toolingRevisionGlobalId: "",
    toolingRevisionSnapshotHash: "",
    toolingSetGlobalId: "",
    toolingSetSnapshotHash: "",
  });
  const returnFocus = useRef<HTMLElement | null>(null);
  const latestCommand = useRef<(() => void) | null>(null);
  const processing = command.kind === "processing";

  const activeCommand: ReviewCommandKind | null = useMemo(() => {
    if (workspace.permissions.beginAnalysis) return "begin_analysis";
    if (workspace.permissions.createComparison) return "create_comparison";
    if (
      latestConclusion?.state === "submitted" &&
      workspace.permissions.decideConclusion
    )
      return "decide_conclusion";
    if (
      (latestConclusion?.state === "approved" ||
        latestConclusion?.state === "rejected") &&
      workspace.permissions.reopenConclusion
    )
      return "reopen_conclusion";
    if (!references.length && workspace.permissions.manageReviewReferences)
      return "create_reference";
    if (workspace.permissions.submitConclusion) return "submit_conclusion";
    if (workspace.permissions.manageReviewReferences) return "create_reference";
    return null;
  }, [latestConclusion?.state, references.length, workspace.permissions]);

  const updateDraft = <Key extends keyof ReviewDraft>(
    key: Key,
    value: ReviewDraft[Key],
  ): void => {
    setDraft((current) => ({ ...current, [key]: value }));
    setDraftDirty(true);
    setFormError(null);
  };

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!draftDirty) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: workspace.trialRound.globalId,
      version: `trial-round-v${String(workspace.trialRound.optimisticVersion)}`,
      returnFocusTarget: () => returnFocus.current,
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [draftDirty, reportWorkspaceDirty, workspace.trialRound]);

  const commandReady = useMemo(() => {
    if (!activeCommand || !latestPolicy || !sessionCommandContext) return false;
    if (activeCommand === "create_comparison")
      return candidateRounds.length >= 2;
    if (activeCommand === "create_reference")
      return (
        Boolean(latestComparison) &&
        [
          draft.fileRevisionGlobalId,
          draft.partRevisionGlobalId,
          draft.toolingRevisionGlobalId,
          draft.toolingSetGlobalId,
        ].every((value) => uuidPattern.test(value.trim())) &&
        [
          draft.fileRevisionSnapshotHash,
          draft.partRevisionSnapshotHash,
          draft.toolingRevisionSnapshotHash,
          draft.toolingSetSnapshotHash,
        ].every((value) => /^[0-9a-f]{64}$/u.test(value.trim()))
      );
    if (activeCommand === "submit_conclusion")
      return (
        Boolean(latestComparison) &&
        references.length >= 1 &&
        Boolean(draft.proposedNextWork.trim()) &&
        Boolean(draft.proposedGateEffect.trim()) &&
        Boolean(draft.proposedNpiEffect.trim())
      );
    return latestConclusion !== null || activeCommand === "begin_analysis";
  }, [
    activeCommand,
    candidateRounds,
    draft,
    latestComparison,
    latestConclusion,
    latestPolicy,
    references.length,
    sessionCommandContext,
  ]);

  const acceptCommand = useCallback(
    (result: TrialReviewCommandResult, label: string): void => {
      onWorkspace(result.workspace);
      setCommand({ kind: "succeeded", label, replayed: result.replayed });
      setDraftDirty(false);
      setReviewOpen(false);
      setFormError(null);
      globalThis.queueMicrotask(() => returnFocus.current?.focus());
    },
    [onWorkspace],
  );

  const runCommand = useCallback(
    (
      label: string,
      operation: (signal: AbortSignal) => Promise<TrialReviewCommandResult>,
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

  const confirmCommand = (reason: string): void => {
    if (
      !activeCommand ||
      !latestPolicy ||
      !sessionCommandContext ||
      !commandReady
    )
      return;
    const commandContext = {
      csrfToken: sessionCommandContext.csrfToken,
      idempotencyKey: `trial-review-${activeCommand}-${globalThis.crypto.randomUUID()}`,
    };
    const policyContext = {
      expectedPolicyRevisionSnapshotHash: latestPolicy.snapshotHash,
      expectedRoundOptimisticVersion: workspace.trialRound.optimisticVersion,
      expectedRoundSnapshotHash: workspace.trialRound.snapshotHash,
      policyRevisionGlobalId: latestPolicy.globalId,
    } as const;
    const label = reviewCommandLabel(t, activeCommand);
    if (activeCommand === "begin_analysis") {
      const value: BeginTrialAnalysisCommand = { ...policyContext, reason };
      runCommand(label, (signal) =>
        dataSource.beginAnalysis(
          projectId,
          workspace.trialRound.globalId,
          value,
          {
            ...commandContext,
            signal,
          },
        ),
      );
      return;
    }
    if (activeCommand === "create_comparison") {
      const value: CreateTrialRoundComparisonCommand = {
        ...policyContext,
        reason,
        rounds: candidateRounds.map((round) => ({
          expectedOptimisticVersion: round.optimisticVersion,
          expectedSnapshotHash: round.snapshotHash,
          trialRoundGlobalId: round.globalId,
        })),
      };
      runCommand(label, (signal) =>
        dataSource.createComparison(
          projectId,
          workspace.trialRound.globalId,
          value,
          { ...commandContext, signal },
        ),
      );
      return;
    }
    if (activeCommand === "create_reference" && latestComparison) {
      const value: CreateTrialReviewReferenceCommand = {
        ...policyContext,
        comparisonSnapshotGlobalId: latestComparison.globalId,
        expectedComparisonSnapshotHash: latestComparison.snapshotHash,
        expectedFileRevisionSnapshotHash: draft.fileRevisionSnapshotHash.trim(),
        expectedPartRevisionSnapshotHash: draft.partRevisionSnapshotHash.trim(),
        expectedToolingRevisionSnapshotHash:
          draft.toolingRevisionSnapshotHash.trim(),
        expectedToolingSetSnapshotHash: draft.toolingSetSnapshotHash.trim(),
        fileRevisionGlobalId: draft.fileRevisionGlobalId.trim(),
        partRevisionGlobalId: draft.partRevisionGlobalId.trim(),
        reason,
        referenceKind: draft.referenceKind,
        toolingMasterGlobalId: workspace.trialRound.toolingMasterGlobalId,
        toolingRevisionGlobalId: draft.toolingRevisionGlobalId.trim(),
        toolingSetGlobalId: draft.toolingSetGlobalId.trim(),
      };
      runCommand(label, (signal) =>
        dataSource.createReviewReference(
          projectId,
          workspace.trialRound.globalId,
          value,
          { ...commandContext, signal },
        ),
      );
      return;
    }
    if (activeCommand === "submit_conclusion" && latestComparison) {
      const value: SubmitTrialConclusionCommand = {
        ...policyContext,
        comparisonSnapshotGlobalId: latestComparison.globalId,
        conclusionCode: draft.conclusionCode,
        expectedComparisonSnapshotHash: latestComparison.snapshotHash,
        proposedGateEffect: draft.proposedGateEffect.trim(),
        proposedNextWork: [draft.proposedNextWork.trim()],
        proposedNpiEffect: draft.proposedNpiEffect.trim(),
        reason,
        reviewReferences: references.map((reference) => ({
          globalId: reference.globalId,
          snapshotHash: reference.snapshotHash,
        })),
      };
      runCommand(label, (signal) =>
        dataSource.submitConclusion(
          projectId,
          workspace.trialRound.globalId,
          value,
          { ...commandContext, signal },
        ),
      );
      return;
    }
    if (activeCommand === "decide_conclusion" && latestConclusion) {
      const value: DecideTrialConclusionCommand = {
        ...policyContext,
        decision: draft.decision,
        expectedConclusionRevisionGlobalId: latestConclusion.globalId,
        expectedConclusionRevisionSnapshotHash: latestConclusion.snapshotHash,
        expectedConclusionVersion: latestConclusion.conclusionVersion,
        reason,
      };
      runCommand(label, (signal) =>
        dataSource.decideConclusion(
          projectId,
          workspace.trialRound.globalId,
          latestConclusion.conclusionGlobalId,
          value,
          { ...commandContext, signal },
        ),
      );
      return;
    }
    if (activeCommand === "reopen_conclusion" && latestConclusion) {
      const value: ReopenTrialConclusionCommand = {
        ...policyContext,
        conclusionGlobalId: latestConclusion.conclusionGlobalId,
        expectedConclusionRevisionGlobalId: latestConclusion.globalId,
        expectedConclusionRevisionSnapshotHash: latestConclusion.snapshotHash,
        expectedConclusionVersion: latestConclusion.conclusionVersion,
        reason,
      };
      runCommand(label, (signal) =>
        dataSource.reopenConclusion(
          projectId,
          workspace.trialRound.globalId,
          value,
          { ...commandContext, signal },
        ),
      );
    }
  };

  const requestReview = (trigger: HTMLElement): void => {
    returnFocus.current = trigger;
    if (!commandReady) {
      setFormError(
        activeCommand === "create_comparison"
          ? t(
              "At least two exact Trial Round snapshots are required for comparison.",
            )
          : t(
              "Complete every required exact reference and proposal field before review.",
            ),
      );
      return;
    }
    setFormError(null);
    setReviewOpen(true);
  };

  return (
    <>
      <Panel title={t("Trial review and conclusion")}>
        <div className="trial-live__command-bar">
          {activeCommand ? (
            <Button
              disabled={processing || !sessionCommandContext}
              id="trial-review-primary-action"
              onClick={(event) => {
                requestReview(event.currentTarget);
              }}
              visual="primary"
            >
              {reviewCommandLabel(t, activeCommand)}
            </Button>
          ) : null}
        </div>
        <DefinitionList
          rows={[
            {
              label: t("Selected Round"),
              value: workspace.trialRound.displayLabel,
              exempt: "identifier",
            },
            {
              label: t("Round state"),
              value: roundStateLabel(t, workspace.trialRound.currentState),
            },
            {
              label: t("Exact policy revision"),
              value: latestPolicy?.globalId ?? t("Unavailable"),
              ...(latestPolicy ? { exempt: "identifier" as const } : {}),
            },
            {
              label: t("Policy snapshot"),
              value: latestPolicy?.snapshotHash ?? t("Unavailable"),
              ...(latestPolicy ? { exempt: "identifier" as const } : {}),
            },
            {
              label: t("Latest comparison snapshot"),
              value: latestComparison?.snapshotHash ?? t("Unavailable"),
              ...(latestComparison ? { exempt: "identifier" as const } : {}),
            },
            {
              label: t("Comparison snapshots"),
              value: formatNumber(
                locale,
                workspace.comparisonSnapshots.length,
                0,
              ),
            },
            {
              label: t("Current review references"),
              value: formatNumber(locale, references.length, 0),
            },
            {
              label: t("Conclusion state"),
              value: latestConclusion
                ? conclusionStateLabel(t, latestConclusion.state)
                : t("Not submitted"),
            },
          ]}
        />
      </Panel>
      {!sessionCommandContext || !workspace.permissions.view ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Trial review is read only in this session.")}</span>
          <span>
            {t(
              "The server rechecks Project membership, exact policy revision and conclusion authority for every command.",
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
              "The exact policy, Round and predecessor snapshots are being verified atomically.",
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
                  "The exact prior review command response was replayed safely.",
                )
              : t("The review command appended immutable audit history.")}
          </span>
        </div>
      ) : null}
      {command.kind === "failed" ? (
        <Panel title={t("Trial review command failed")}>
          <RequestFailurePanel failure={command.failure} />
          {canRetry(command.failure) ? (
            <Button onClick={() => latestCommand.current?.()}>
              {t("Retry")}
            </Button>
          ) : null}
        </Panel>
      ) : null}
      {formError ? (
        <div className="form-error" role="alert">
          {formError}
        </div>
      ) : null}
      {activeCommand === "create_reference" ? (
        <Panel title={t("Exact review reference input")}>
          <div className="trial-live__review-form">
            <label>
              <span>{t("Reference kind")}</span>
              <Select
                onChange={(event) => {
                  updateDraft(
                    "referenceKind",
                    event.target.value as TrialReviewReferenceKind,
                  );
                }}
                value={draft.referenceKind}
              >
                {trialReviewReferenceKinds.map((kind) => (
                  <option key={kind} value={kind}>
                    {reviewReferenceKindLabel(t, kind)}
                  </option>
                ))}
              </Select>
            </label>
            {(
              [
                ["partRevisionGlobalId", t("Part revision stable ID")],
                ["partRevisionSnapshotHash", t("Part revision snapshot")],
                ["toolingRevisionGlobalId", t("Tooling revision stable ID")],
                ["toolingRevisionSnapshotHash", t("Tooling revision snapshot")],
                ["toolingSetGlobalId", t("Tooling Set stable ID")],
                ["toolingSetSnapshotHash", t("Tooling Set snapshot")],
                ["fileRevisionGlobalId", t("File revision stable ID")],
                ["fileRevisionSnapshotHash", t("File revision snapshot")],
              ] as const
            ).map(([key, label]) => (
              <label key={key}>
                <span>{label}</span>
                <TextInput
                  onChange={(event) => {
                    updateDraft(key, event.target.value);
                  }}
                  value={draft[key]}
                />
              </label>
            ))}
          </div>
        </Panel>
      ) : null}
      {activeCommand === "submit_conclusion" ? (
        <Panel title={t("Conclusion proposal input")}>
          <div className="trial-live__review-form">
            <label>
              <span>{t("Conclusion code")}</span>
              <Select
                onChange={(event) => {
                  updateDraft(
                    "conclusionCode",
                    event.target.value as TrialConclusionCode,
                  );
                }}
                value={draft.conclusionCode}
              >
                {(
                  latestPolicy?.allowedConclusionCodes ?? trialConclusionCodes
                ).map((code) => (
                  <option key={code} value={code}>
                    {conclusionCodeLabel(t, code)}
                  </option>
                ))}
              </Select>
            </label>
            {(
              [
                ["proposedNextWork", t("Proposed next work")],
                ["proposedGateEffect", t("Proposed Gate effect")],
                ["proposedNpiEffect", t("Proposed NPI effect")],
              ] as const
            ).map(([key, label]) => (
              <label key={key}>
                <span>{label}</span>
                <textarea
                  maxLength={1000}
                  onChange={(event) => {
                    updateDraft(key, event.target.value);
                  }}
                  value={draft[key]}
                />
              </label>
            ))}
          </div>
        </Panel>
      ) : null}
      {activeCommand === "decide_conclusion" ? (
        <Panel title={t("Independent conclusion decision")}>
          <label className="trial-live__review-decision">
            <span>{t("Decision")}</span>
            <Select
              onChange={(event) => {
                updateDraft(
                  "decision",
                  event.target.value as ReviewDraft["decision"],
                );
              }}
              value={draft.decision}
            >
              <option value="approved">{t("Approve")}</option>
              <option value="rejected">{t("Reject")}</option>
            </Select>
          </label>
        </Panel>
      ) : null}
      {latestComparison ? (
        <>
          <Panel
            className="desktop-engineering-only"
            title={t("Exact Round input comparison")}
          >
            <table
              aria-label={t("Exact Round input comparison")}
              className="data-table trial-live__comparison-table"
              tabIndex={0}
            >
              <thead>
                <tr>
                  <th>{t("Input key")}</th>
                  <th>{t("Change")}</th>
                  {latestComparison.sources.map((sourceItem) => (
                    <th key={sourceItem.trialRoundGlobalId}>
                      {t("Round {{sequence}}", {
                        sequence: sourceItem.sequence,
                      })}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {latestComparison.inputRows.map((row) => (
                  <tr key={row.semanticKey}>
                    <td data-language-exempt="identifier">{row.semanticKey}</td>
                    <td>
                      {row.changeState === "added"
                        ? t("Added")
                        : row.changeState === "removed"
                          ? t("Removed")
                          : row.changeState === "changed"
                            ? t("Changed")
                            : t("Same")}
                    </td>
                    {row.cells.map((cell) => (
                      <td
                        data-language-exempt="business-data"
                        key={cell.trialRoundGlobalId}
                      >
                        {cell.canonicalValue ?? t("Unavailable")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <Panel
            className="desktop-engineering-only"
            title={t("Performance and dimension comparison")}
          >
            <table
              aria-label={t("Performance and dimension comparison")}
              className="data-table trial-live__comparison-table"
              tabIndex={0}
            >
              <thead>
                <tr>
                  <th>{t("Metric")}</th>
                  <th>{t("Unit state")}</th>
                  {latestComparison.sources.map((sourceItem) => (
                    <th key={sourceItem.trialRoundGlobalId}>
                      {t("Round {{sequence}}", {
                        sequence: sourceItem.sequence,
                      })}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {latestComparison.metricRows.map((row) => (
                  <tr
                    key={`${row.metricKind}-${row.metricKey}-${row.cavityGlobalId ?? "all"}`}
                  >
                    <td>
                      <strong data-language-exempt="identifier">
                        {row.metricKey}
                      </strong>
                      <small className="trial-live__resource-reference">
                        {row.metricKind === "parameter"
                          ? t("Parameter")
                          : row.metricKind === "dimension"
                            ? t("Dimension")
                            : row.metricKind === "cycle_time"
                              ? t("Cycle time")
                              : t("Yield")}
                      </small>
                    </td>
                    <td>
                      {row.unitState === "comparable"
                        ? t("Comparable")
                        : row.unitState === "unit_mismatch"
                          ? t("Unit mismatch")
                          : t("Unavailable")}
                    </td>
                    {row.cells.map((cell) => (
                      <td key={cell.trialRoundGlobalId}>
                        <SemanticStatus
                          label={
                            cell.comparisonState === "within_spec"
                              ? t("Within specification")
                              : cell.comparisonState === "out_of_spec"
                                ? t("Out of specification")
                                : cell.state === "not_measured"
                                  ? t("Not measured")
                                  : cell.state === "unavailable"
                                    ? t("Unavailable")
                                    : t("Measured")
                          }
                          tone={
                            cell.comparisonState === "out_of_spec"
                              ? "warning"
                              : "info"
                          }
                        />
                        <span data-language-exempt="business-data">
                          {cell.value ?? "—"} {cell.unit ?? ""}
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <Panel
            className="desktop-engineering-only"
            title={t("Defect trend across compared Rounds")}
          >
            {latestComparison.defectTrends.length ? (
              <table
                aria-label={t("Defect trend across compared Rounds")}
                className="data-table"
                tabIndex={0}
              >
                <thead>
                  <tr>
                    <th>{t("Defect")}</th>
                    <th>{t("Trend")}</th>
                  </tr>
                </thead>
                <tbody>
                  {latestComparison.defectTrends.map((trend) => (
                    <tr key={trend.defectGlobalId}>
                      <td data-language-exempt="identifier">
                        {trend.defectGlobalId}
                      </td>
                      <td>
                        {trend.state === "new"
                          ? t("New")
                          : trend.state === "continued"
                            ? t("Continued")
                            : trend.state === "resolved"
                              ? t("Resolved")
                              : t("Reopened")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-state" role="status">
                <strong>
                  {t("No defect trend is present in this comparison.")}
                </strong>
              </div>
            )}
          </Panel>
        </>
      ) : (
        <Panel
          className="desktop-engineering-only"
          title={t("Exact Round comparison")}
        >
          <div className="empty-state" role="status">
            <strong>{t("No immutable Round comparison is available.")}</strong>
            <span>
              {t(
                "Begin analysis and compare at least two exact Round snapshots under one policy revision.",
              )}
            </span>
          </div>
        </Panel>
      )}
      <Panel
        className="desktop-engineering-only"
        title={t("Controlled review references")}
      >
        {references.length ? (
          <table
            aria-label={t("Controlled review references")}
            className="data-table"
            tabIndex={0}
          >
            <thead>
              <tr>
                <th>{t("Reference kind")}</th>
                <th>{t("Version")}</th>
                <th>{t("Part revision")}</th>
                <th>{t("Tooling revision")}</th>
                <th>{t("File revision")}</th>
                <th>{t("Approval authority")}</th>
              </tr>
            </thead>
            <tbody>
              {references.map((reference) => (
                <tr key={reference.globalId}>
                  <td>
                    {reviewReferenceKindLabel(t, reference.referenceKind)}
                  </td>
                  <td>{formatNumber(locale, reference.referenceVersion, 0)}</td>
                  <td data-language-exempt="identifier">
                    {reference.partRevision.globalId}
                  </td>
                  <td data-language-exempt="identifier">
                    {reference.toolingRevision.globalId}
                  </td>
                  <td data-language-exempt="identifier">
                    {reference.fileRevision.globalId}
                  </td>
                  <td>
                    <SemanticStatus label={t("Unavailable")} tone="warning" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state" role="status">
            <strong>{t("No controlled review reference is bound.")}</strong>
            <span>
              {t(
                "A conclusion cannot be submitted until every policy-required reference kind is bound to exact revisions.",
              )}
            </span>
          </div>
        )}
      </Panel>
      {latestConclusion ? (
        <>
          <Panel title={t("One-page conclusion summary")}>
            <div className="trial-live__summary-grid">
              <section>
                <h3>{t("Conclusion")}</h3>
                <SemanticStatus
                  label={conclusionStateLabel(t, latestConclusion.state)}
                  tone={
                    latestConclusion.state === "approved"
                      ? "success"
                      : "warning"
                  }
                />
                <p>{conclusionCodeLabel(t, latestConclusion.conclusionCode)}</p>
              </section>
              <section>
                <h3>{t("Input changes")}</h3>
                <p>
                  {t("{{changed}} changed, {{same}} unchanged", {
                    changed: formatNumber(
                      locale,
                      latestConclusion.summaryInput.inputChangeCounts.changed,
                      0,
                    ),
                    same: formatNumber(
                      locale,
                      latestConclusion.summaryInput.inputChangeCounts.same,
                      0,
                    ),
                  })}
                </p>
              </section>
              <section>
                <h3>{t("Cycle time")}</h3>
                <p>
                  {reviewResultStateLabel(
                    t,
                    latestConclusion.summaryInput.cycleTimeState,
                  )}
                </p>
              </section>
              <section>
                <h3>{t("Yield")}</h3>
                <p>
                  {reviewResultStateLabel(
                    t,
                    latestConclusion.summaryInput.yieldState,
                  )}
                </p>
              </section>
            </div>
            <DefinitionList
              rows={[
                {
                  label: t("Proposed next work"),
                  value: latestConclusion.proposedNextWork.join("; "),
                  exempt: "business-data",
                },
                {
                  label: t("Proposed Gate effect"),
                  value: latestConclusion.proposedGateEffect,
                  exempt: "business-data",
                },
                {
                  label: t("Proposed NPI effect"),
                  value: latestConclusion.proposedNpiEffect,
                  exempt: "business-data",
                },
              ]}
            />
          </Panel>
          <Panel title={t("Policy blockers")}>
            {latestConclusion.blockers.length ? (
              <table
                aria-label={t("Policy blockers")}
                className="data-table"
                tabIndex={0}
              >
                <thead>
                  <tr>
                    <th>{t("Blocking rule")}</th>
                    <th>{t("Exact source")}</th>
                  </tr>
                </thead>
                <tbody>
                  {latestConclusion.blockers.map((blocker) => (
                    <tr key={`${blocker.code}-${blocker.sourceKey}`}>
                      <td>
                        <SemanticStatus
                          label={reviewBlockerLabel(t, blocker.code)}
                          tone="warning"
                        />
                      </td>
                      <td data-language-exempt="identifier">
                        {blocker.sourceKey}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-state" role="status">
                <strong>{t("No policy blocker is recorded.")}</strong>
              </div>
            )}
          </Panel>
          <Panel
            className="desktop-engineering-only"
            title={t("Immutable conclusion history")}
          >
            <table
              aria-label={t("Immutable conclusion history")}
              className="data-table"
              tabIndex={0}
            >
              <thead>
                <tr>
                  <th>{t("Version")}</th>
                  <th>{t("State")}</th>
                  <th>{t("Conclusion code")}</th>
                  <th>{t("Reason")}</th>
                  <th>{t("Created by")}</th>
                  <th>{t("Created at")}</th>
                </tr>
              </thead>
              <tbody>
                {workspace.conclusionRevisions.map((revision) => (
                  <tr key={revision.globalId}>
                    <td>
                      {formatNumber(locale, revision.conclusionVersion, 0)}
                    </td>
                    <td>{conclusionStateLabel(t, revision.state)}</td>
                    <td>{conclusionCodeLabel(t, revision.conclusionCode)}</td>
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
        </>
      ) : (
        <Panel title={t("One-page conclusion summary")}>
          <div className="empty-state" role="status">
            <strong>{t("No conclusion proposal has been submitted.")}</strong>
          </div>
        </Panel>
      )}
      <Panel title={t("External decision effects")}>
        <div className="trial-live__external-effects">
          {[
            t("Formal ERP quality"),
            t("Customer signature"),
            t("Gate decision"),
            t("NPI readiness"),
            t("Tooling lifecycle"),
          ].map((label) => (
            <div className="trial-live__later-item" key={label}>
              <SemanticStatus label={t("Unavailable")} tone="neutral" />
              <span>{label}</span>
            </div>
          ))}
          <div className="trial-live__later-item">
            <SemanticStatus label={t("Proposal only")} tone="info" />
            <span>{t("Next work")}</span>
          </div>
        </div>
        <p className="context-help">
          {t(
            "This review records an NPI One proposal only. It does not create ERP quality, customer signature, Gate, readiness or Tooling lifecycle truth.",
          )}
        </p>
      </Panel>
      {reviewOpen && activeCommand ? (
        <ImpactReview
          confirmLabel={reviewCommandLabel(t, activeCommand)}
          details={{
            objectIdentity: workspace.trialRound.globalId,
            version: `v${String(workspace.trialRound.optimisticVersion)}`,
            impact: t(
              "Appends immutable Trial review history against exact policy, Round, comparison and predecessor snapshots.",
            ),
            permission: t(
              "The server rechecks Project membership and the policy-bound submit, decide or reopen authority.",
            ),
            irreversible: t(
              "Committed review revisions are never overwritten by generic CRUD.",
            ),
            failureHandling: t(
              "A failed command changes no review state and can be retried with the same idempotency key.",
            ),
            audit: t(
              "Actor, reason, request, trace and every exact snapshot reference are retained.",
            ),
          }}
          onCancel={() => {
            setReviewOpen(false);
          }}
          onConfirm={confirmCommand}
          reasonMaxLength={2000}
          returnFocusTarget={() => returnFocus.current}
          title={t("Review immutable Trial conclusion command")}
        />
      ) : null}
    </>
  );
}

type ReleasedSummaryCommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "succeeded"; label: string; replayed: boolean }
  | {
      kind: "accepted_refresh_failed";
      label: string;
      replayed: boolean;
      failure: RequestFailure;
    }
  | { kind: "failed"; failure: RequestFailure };

const releasedSummaryFactGroups: readonly ReleasedTrialSummaryFactGroup[] = [
  "inputChanges",
  "actualParameters",
  "samples",
  "cavityResults",
  "defects",
  "comparison",
  "controlledReferences",
  "blockers",
];
const releasedSummaryPageSize = 50;

function releasedSummarySourceLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: ReleasedTrialSummarySourceKind,
): string {
  switch (kind) {
    case "trial_plan_revision":
      return t("Trial Plan revision");
    case "trial_round":
      return t("Trial Round");
    case "trial_input_lock_revision":
      return t("Input lock revision");
    case "trial_actual_revision":
      return t("Trial Actual revision");
    case "trial_sample_batch_revision":
      return t("Sample Batch revision");
    case "trial_cavity_result_revision":
      return t("Cavity Result revision");
    case "tooling_defect_revision":
      return t("Tooling defect revision");
    case "trial_defect_revision":
      return t("Trial defect revision");
    case "trial_defect_verification_revision":
      return t("Defect verification revision");
    case "trial_round_comparison_snapshot":
      return t("Round comparison snapshot");
    case "trial_review_reference_revision":
      return t("Review reference revision");
    case "trial_conclusion_revision":
      return t("Trial conclusion revision");
  }
}

function releasedSummaryFactGroupLabel(
  t: ReturnType<typeof useI18n>["t"],
  group: ReleasedTrialSummaryFactGroup,
): string {
  switch (group) {
    case "inputChanges":
      return t("Input changes");
    case "actualParameters":
      return t("Actual parameters");
    case "samples":
      return t("Samples");
    case "cavityResults":
      return t("Cavity results");
    case "defects":
      return t("Defects and actions");
    case "comparison":
      return t("Round comparison");
    case "controlledReferences":
      return t("Controlled references");
    case "blockers":
      return t("Technical blockers");
  }
}

function releasedSummaryFactStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: ReleasedTrialSummaryFactState,
): string {
  switch (state) {
    case "measured":
      return t("Measured");
    case "not_measured":
      return t("Not measured");
    case "unavailable":
      return t("Unavailable");
    case "satisfied":
      return t("Satisfied");
    case "failed":
      return t("Failed");
    case "open":
      return t("Open");
    case "closed":
      return t("Closed");
    case "informational":
      return t("Informational");
  }
}

function releasedSummaryActionLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: "retain" | "revise",
): string {
  return kind === "retain"
    ? t("Retain technical summary")
    : t("Revise technical summary");
}

function isReleasedSummaryOverflow(failure: RequestFailure): boolean {
  const code = failure.problem?.code ?? "";
  return code.includes("OVERFLOW") || code.includes("TOO_LARGE");
}

function ReleasedTrialSummarySection({
  controlledPrintDataSource,
  dataSource,
  onWorkspace,
  projectId,
  reportWorkspaceDirty,
  workspace,
}: {
  controlledPrintDataSource?: ControlledPrintDataSource | undefined;
  dataSource: TrialDataSource;
  onWorkspace: (value: ReleasedTrialSummaryWorkspace) => void;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  workspace: ReleasedTrialSummaryWorkspace;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const currentRevision = workspace.summaryRevisions.at(-1) ?? null;
  const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(
    workspace.currentSummaryRevisionGlobalId,
  );
  const [factGroup, setFactGroup] =
    useState<ReleasedTrialSummaryFactGroup>("inputChanges");
  const [factPage, setFactPage] = useState(0);
  const [sourcePage, setSourcePage] = useState(0);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [command, setCommand] = useState<ReleasedSummaryCommandState>({
    kind: "idle",
  });
  const returnFocus = useRef<HTMLElement | null>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const idempotencyKey = useRef<string | null>(null);
  const latestCommand = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      activeRequest.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!reviewOpen && command.kind !== "processing") {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity:
        currentRevision?.globalId ?? workspace.trialRound.globalId,
      version: currentRevision
        ? `released-summary-v${String(currentRevision.summaryVersion)}`
        : `trial-round-v${String(workspace.trialRound.optimisticVersion)}`,
      returnFocusTarget: () => returnFocus.current,
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [
    command.kind,
    currentRevision,
    reportWorkspaceDirty,
    reviewOpen,
    workspace.trialRound,
  ]);

  const selectedRevision =
    workspace.summaryRevisions.find(
      (revision) => revision.globalId === selectedRevisionId,
    ) ?? currentRevision;
  const currentConclusion = workspace.currentDecidedConclusion;
  const actionKind = useMemo<"retain" | "revise" | null>(() => {
    if (
      currentRevision === null &&
      currentConclusion !== null &&
      workspace.permissions.retain
    )
      return "retain";
    if (
      currentRevision !== null &&
      currentConclusion !== null &&
      workspace.permissions.revise &&
      (currentRevision.conclusionRevisionGlobalId !==
        currentConclusion.globalId ||
        currentRevision.conclusionSnapshotHash !==
          currentConclusion.snapshotHash)
    )
      return "revise";
    return null;
  }, [currentConclusion, currentRevision, workspace.permissions]);

  const reloadWorkspace = useCallback((): void => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    void dataSource
      .loadReleasedTrialSummaries(
        projectId,
        workspace.trialRound.globalId,
        controller.signal,
      )
      .then((value) => {
        if (controller.signal.aborted || activeRequest.current !== controller)
          return;
        activeRequest.current = null;
        onWorkspace(value);
        setSelectedRevisionId(value.currentSummaryRevisionGlobalId);
        setCommand({ kind: "idle" });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          activeRequest.current !== controller ||
          error instanceof TrialRequestCancelledError
        )
          return;
        activeRequest.current = null;
        setCommand({ kind: "failed", failure: toRequestFailure(error) });
      });
  }, [dataSource, onWorkspace, projectId, workspace.trialRound.globalId]);

  const acceptCommand = useCallback(
    (result: ReleasedTrialSummaryCommandResult, label: string): void => {
      onWorkspace(result.workspace);
      setSelectedRevisionId(result.workspace.currentSummaryRevisionGlobalId);
      setReviewOpen(false);
      idempotencyKey.current = null;
      const controller = new AbortController();
      activeRequest.current = controller;
      void dataSource
        .loadReleasedTrialSummaries(
          projectId,
          result.workspace.trialRound.globalId,
          controller.signal,
        )
        .then((value) => {
          if (controller.signal.aborted || activeRequest.current !== controller)
            return;
          activeRequest.current = null;
          onWorkspace(value);
          setSelectedRevisionId(value.currentSummaryRevisionGlobalId);
          setCommand({ kind: "succeeded", label, replayed: result.replayed });
          globalThis.queueMicrotask(() => returnFocus.current?.focus());
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            activeRequest.current !== controller ||
            error instanceof TrialRequestCancelledError
          )
            return;
          activeRequest.current = null;
          setCommand({
            failure: toRequestFailure(error),
            kind: "accepted_refresh_failed",
            label,
            replayed: result.replayed,
          });
          globalThis.queueMicrotask(() => returnFocus.current?.focus());
        });
    },
    [dataSource, onWorkspace, projectId],
  );

  const confirmCommand = (reason: string): void => {
    if (!actionKind || !currentConclusion || !sessionCommandContext) return;
    const label = releasedSummaryActionLabel(t, actionKind);
    const key =
      idempotencyKey.current ??
      `released-summary-${actionKind}-${globalThis.crypto.randomUUID()}`;
    idempotencyKey.current = key;
    const baseCommand: RetainReleasedTrialSummaryCommand = {
      conclusionRevisionGlobalId: currentConclusion.globalId,
      expectedConclusionSnapshotHash: currentConclusion.snapshotHash,
      expectedConclusionVersion: currentConclusion.conclusionVersion,
      expectedRoundOptimisticVersion: workspace.trialRound.optimisticVersion,
      expectedRoundSnapshotHash: workspace.trialRound.snapshotHash,
      reason,
    };
    const execute = (): void => {
      activeRequest.current?.abort();
      const controller = new AbortController();
      activeRequest.current = controller;
      setCommand({ kind: "processing", label });
      const context = {
        csrfToken: sessionCommandContext.csrfToken,
        idempotencyKey: key,
        signal: controller.signal,
      };
      let request: Promise<ReleasedTrialSummaryCommandResult>;
      if (actionKind === "retain") {
        request = dataSource.retainReleasedTrialSummary(
          projectId,
          workspace.trialRound.globalId,
          baseCommand,
          context,
        );
      } else {
        if (!currentRevision) return;
        request = dataSource.reviseReleasedTrialSummary(
          projectId,
          workspace.trialRound.globalId,
          currentRevision.summaryGlobalId,
          {
            ...baseCommand,
            expectedPredecessorSnapshotHash: currentRevision.snapshotHash,
            expectedPredecessorVersion: currentRevision.summaryVersion,
            predecessorRevisionGlobalId: currentRevision.globalId,
          } satisfies ReviseReleasedTrialSummaryCommand,
          context,
        );
      }
      void request
        .then((result) => {
          if (controller.signal.aborted || activeRequest.current !== controller)
            return;
          activeRequest.current = null;
          acceptCommand(result, label);
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            activeRequest.current !== controller ||
            error instanceof TrialRequestCancelledError
          )
            return;
          activeRequest.current = null;
          setReviewOpen(false);
          setCommand({ kind: "failed", failure: toRequestFailure(error) });
        });
    };
    latestCommand.current = execute;
    execute();
  };

  const facts = selectedRevision?.presentationProjection.facts[factGroup] ?? [];
  const factPageCount = Math.max(
    1,
    Math.ceil(facts.length / releasedSummaryPageSize),
  );
  const sourceManifest = selectedRevision?.sourceManifest ?? [];
  const sourcePageCount = Math.max(
    1,
    Math.ceil(sourceManifest.length / releasedSummaryPageSize),
  );
  const visibleFacts = facts.slice(
    factPage * releasedSummaryPageSize,
    (factPage + 1) * releasedSummaryPageSize,
  );
  const visibleSources = sourceManifest.slice(
    sourcePage * releasedSummaryPageSize,
    (sourcePage + 1) * releasedSummaryPageSize,
  );
  return (
    <section
      aria-label={t("Released Trial Summary")}
      className="released-summary-workspace"
    >
      <div className="released-summary-workspace__toolbar">
        <div className="released-summary-workspace__title">
          <strong>{t("Released Trial Summary")}</strong>
          <span className="released-summary-workspace__subtitle">
            {t(
              "Immutable technical retention from the exact decided conclusion",
            )}
          </span>
        </div>
        {actionKind ? (
          <Button
            disabled={
              command.kind === "processing" || sessionCommandContext === null
            }
            id="released-summary-primary-action"
            onClick={(event) => {
              returnFocus.current = event.currentTarget;
              setReviewOpen(true);
            }}
            visual="primary"
          >
            {releasedSummaryActionLabel(t, actionKind)}
          </Button>
        ) : null}
      </div>

      {!sessionCommandContext ||
      (!workspace.permissions.retain && !workspace.permissions.revise) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Released Summary is read only in this session.")}</span>
          <span>
            {t(
              "The server rechecks Project visibility and exact technical authority for every retain or revise command.",
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
              "The exact Round, decided conclusion, predecessor and source graph are being verified atomically.",
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
                  "The exact prior summary command response was replayed safely.",
                )
              : t(
                  "The technical summary and audit history were retained immutably.",
                )}
          </span>
        </div>
      ) : null}
      {command.kind === "accepted_refresh_failed" ? (
        <Panel
          title={t("Summary retained; current history could not be refreshed")}
        >
          <p>
            {command.replayed
              ? t(
                  "The server replayed the accepted command. Do not submit it again.",
                )
              : t("The server accepted the command. Do not submit it again.")}
          </p>
          <RequestFailurePanel failure={command.failure} />
          <Button onClick={reloadWorkspace}>
            {t("Reload summary history")}
          </Button>
        </Panel>
      ) : null}
      {command.kind === "failed" ? (
        <Panel
          title={
            isReleasedSummaryOverflow(command.failure)
              ? t("Summary source graph exceeds the safe retention boundary")
              : t("Released Summary command failed")
          }
        >
          <RequestFailurePanel failure={command.failure} />
          {command.failure.problem?.status === 409 ? (
            <Button onClick={reloadWorkspace}>
              {t("Reload current summary")}
            </Button>
          ) : canRetry(command.failure) ? (
            <Button onClick={() => latestCommand.current?.()}>
              {t("Retry exact command")}
            </Button>
          ) : null}
        </Panel>
      ) : null}

      <div className="released-summary-workspace__layout">
        <Panel
          bodyClassName="released-summary-workspace__history-body"
          className="released-summary-workspace__history"
          title={t("Immutable summary history")}
        >
          {workspace.summaryRevisions.length ? (
            <ol>
              {[...workspace.summaryRevisions].reverse().map((revision) => (
                <li key={revision.globalId}>
                  <button
                    aria-current={
                      selectedRevision?.globalId === revision.globalId
                        ? "page"
                        : undefined
                    }
                    className="released-summary-workspace__history-select"
                    onClick={() => {
                      setSelectedRevisionId(revision.globalId);
                      setFactPage(0);
                      setSourcePage(0);
                    }}
                    type="button"
                  >
                    <strong>
                      {t("Version")}{" "}
                      {formatNumber(locale, revision.summaryVersion, 0)}
                    </strong>
                    <span className="released-summary-workspace__history-state">
                      {conclusionStateLabel(t, revision.conclusionState)}
                    </span>
                    <time
                      className="released-summary-workspace__history-time"
                      dateTime={revision.createdAt}
                    >
                      {formatDateTime(locale, revision.createdAt)}
                    </time>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <div className="empty-state" role="status">
              <strong>{t("No technical summary has been retained.")}</strong>
              <span>
                {currentConclusion
                  ? t(
                      "The current decided conclusion is eligible for technical retention when authority is available.",
                    )
                  : t(
                      "A unique current approved or rejected conclusion is required first.",
                    )}
              </span>
            </div>
          )}
        </Panel>

        <div className="released-summary-workspace__content">
          {selectedRevision ? (
            <>
              <Panel
                actions={
                  controlledPrintDataSource ? (
                    <ControlledPrintAction
                      dataSource={controlledPrintDataSource}
                      projectId={projectId}
                      source={{
                        sourceGlobalId: selectedRevision.globalId,
                        sourceKind: "released_trial_summary",
                        sourceVersion: selectedRevision.summaryVersion,
                      }}
                    />
                  ) : undefined
                }
                title={t("Selected technical summary")}
              >
                <DefinitionList
                  rows={[
                    {
                      label: t("Summary stable ID"),
                      value: selectedRevision.summaryGlobalId,
                      exempt: "identifier",
                    },
                    {
                      label: t("Revision stable ID"),
                      value: selectedRevision.globalId,
                      exempt: "identifier",
                    },
                    {
                      label: t("Conclusion state"),
                      value: conclusionStateLabel(
                        t,
                        selectedRevision.conclusionState,
                      ),
                    },
                    {
                      label: t("Conclusion"),
                      value: conclusionCodeLabel(
                        t,
                        selectedRevision.conclusionCode,
                      ),
                    },
                    {
                      label: t("Source manifest entries"),
                      value: formatNumber(
                        locale,
                        selectedRevision.sourceManifest.length,
                        0,
                      ),
                    },
                    {
                      label: t("Controlled output mapping"),
                      value: t("Unavailable"),
                    },
                    {
                      label: t("Retained by"),
                      value: selectedRevision.createdByUserId,
                      exempt: "business-data",
                    },
                  ]}
                />
                <p className="released-summary-workspace__disclaimer">
                  {t(
                    "This is an NPI-owned technical summary. It is not approval, signature, production acceptance, Gate truth or external publication.",
                  )}
                </p>
              </Panel>

              <Panel
                className="desktop-engineering-only"
                title={t("Safe presentation facts")}
              >
                <label className="field-control">
                  <span>{t("Fact group")}</span>
                  <Select
                    onChange={(event) => {
                      setFactGroup(
                        event.target.value as ReleasedTrialSummaryFactGroup,
                      );
                      setFactPage(0);
                    }}
                    value={factGroup}
                  >
                    {releasedSummaryFactGroups.map((group) => (
                      <option key={group} value={group}>
                        {releasedSummaryFactGroupLabel(t, group)} (
                        {formatNumber(
                          locale,
                          selectedRevision.presentationProjection.facts[group]
                            .length,
                          0,
                        )}
                        )
                      </option>
                    ))}
                  </Select>
                </label>
                {visibleFacts.length ? (
                  <div
                    aria-label={t("Safe presentation facts")}
                    className="released-summary-workspace__table-body"
                    tabIndex={0}
                  >
                    <table>
                      <thead>
                        <tr>
                          <th>{t("Fact")}</th>
                          <th>{t("State")}</th>
                          <th>{t("Value")}</th>
                          <th>{t("Unit")}</th>
                          <th>{t("Sources")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleFacts.map((fact, index) => (
                          <tr
                            key={`${fact.factKey}:${String(index + factPage * releasedSummaryPageSize)}`}
                          >
                            <td data-language-exempt="business-data">
                              {fact.factKey}
                            </td>
                            <td>
                              {releasedSummaryFactStateLabel(
                                t,
                                fact.valueState,
                              )}
                            </td>
                            <td data-language-exempt="business-data">
                              {fact.value === null
                                ? t("Unavailable")
                                : typeof fact.value === "boolean"
                                  ? fact.value
                                    ? t("Yes")
                                    : t("No")
                                  : typeof fact.value === "number"
                                    ? formatNumber(locale, fact.value, 2)
                                    : fact.value}
                            </td>
                            <td data-language-exempt="identifier">
                              {fact.unit ?? "—"}
                            </td>
                            <td>
                              {formatNumber(
                                locale,
                                fact.sourceReferences.length,
                                0,
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p>{t("No facts are retained in this group.")}</p>
                )}
                <div className="released-summary-workspace__pagination">
                  <Button
                    disabled={factPage === 0}
                    onClick={() => {
                      setFactPage((page) => Math.max(0, page - 1));
                    }}
                  >
                    {t("Previous")}
                  </Button>
                  <span>
                    {t("Page")} {formatNumber(locale, factPage + 1, 0)} /{" "}
                    {formatNumber(locale, factPageCount, 0)}
                  </span>
                  <Button
                    disabled={factPage + 1 >= factPageCount}
                    onClick={() => {
                      setFactPage((page) =>
                        Math.min(factPageCount - 1, page + 1),
                      );
                    }}
                  >
                    {t("Next")}
                  </Button>
                </div>
              </Panel>

              <Panel
                className="desktop-engineering-only"
                title={t("Exact source manifest")}
              >
                <div
                  aria-label={t("Exact source manifest")}
                  className="released-summary-workspace__table-body"
                  tabIndex={0}
                >
                  <table>
                    <thead>
                      <tr>
                        <th>{t("Source kind")}</th>
                        <th>{t("Stable ID")}</th>
                        <th>{t("Version")}</th>
                        <th>{t("Snapshot hash")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleSources.map((source) => (
                        <tr key={`${source.kind}:${source.globalId}`}>
                          <td>{releasedSummarySourceLabel(t, source.kind)}</td>
                          <td data-language-exempt="identifier">
                            {source.globalId}
                          </td>
                          <td>
                            {formatNumber(locale, source.sourceVersion, 0)}
                          </td>
                          <td data-language-exempt="identifier">
                            <code>{source.snapshotHash}</code>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="released-summary-workspace__pagination">
                  <Button
                    disabled={sourcePage === 0}
                    onClick={() => {
                      setSourcePage((page) => Math.max(0, page - 1));
                    }}
                  >
                    {t("Previous")}
                  </Button>
                  <span>
                    {t("Page")} {formatNumber(locale, sourcePage + 1, 0)} /{" "}
                    {formatNumber(locale, sourcePageCount, 0)}
                  </span>
                  <Button
                    disabled={sourcePage + 1 >= sourcePageCount}
                    onClick={() => {
                      setSourcePage((page) =>
                        Math.min(sourcePageCount - 1, page + 1),
                      );
                    }}
                  >
                    {t("Next")}
                  </Button>
                </div>
              </Panel>
            </>
          ) : (
            <Panel
              className="desktop-engineering-only"
              title={t("Selected technical summary")}
            >
              <div className="empty-state" role="status">
                <strong>
                  {t("No immutable summary revision is available.")}
                </strong>
              </div>
            </Panel>
          )}
        </div>

        <DockedInspector title={t("Summary authority inspector")}>
          <DefinitionList
            rows={[
              {
                label: t("Current decided conclusion"),
                value: currentConclusion
                  ? conclusionStateLabel(t, currentConclusion.state)
                  : t("Unavailable"),
              },
              {
                label: t("Exact predecessor required"),
                value: t("Yes"),
              },
              {
                label: t("Redaction rules applied"),
                value: selectedRevision
                  ? formatNumber(
                      locale,
                      selectedRevision.redactionManifest.appliedRuleCodes
                        .length,
                      0,
                    )
                  : t("Unavailable"),
              },
              {
                label: t("Sensitive field classes excluded"),
                value: selectedRevision
                  ? formatNumber(
                      locale,
                      selectedRevision.redactionManifest
                        .excludedSensitiveFieldClasses.length,
                      0,
                    )
                  : t("Unavailable"),
              },
              {
                label: t("External projection"),
                value: t("Unavailable"),
              },
              {
                label: t("Formal release"),
                value: t("Unavailable"),
              },
              {
                label: t("Customer approval"),
                value: t("Unavailable"),
              },
              {
                label: t("Signature"),
                value: t("Unavailable"),
              },
              {
                label: t("Production acceptance"),
                value: t("Unavailable"),
              },
              {
                label: t("Gate decision"),
                value: t("Unavailable"),
              },
            ]}
          />
          <p className="context-help">
            {t(
              "Structural redaction excludes private locators, file content, credentials, provider payloads and unapproved external projection.",
            )}
          </p>
        </DockedInspector>
      </div>

      {reviewOpen && actionKind ? (
        <ImpactReview
          confirmLabel={releasedSummaryActionLabel(t, actionKind)}
          contextRows={[
            {
              exempt: "identifier",
              label: t("Round snapshot"),
              value: workspace.trialRound.snapshotHash,
            },
            {
              exempt: "identifier",
              label: t("Conclusion snapshot"),
              value: currentConclusion?.snapshotHash ?? "—",
            },
          ]}
          details={{
            objectIdentity: workspace.trialRound.globalId,
            version: currentRevision
              ? `v${String(currentRevision.summaryVersion)}`
              : t("New summary stream"),
            impact: t(
              "Appends one immutable technical summary from the exact complete source graph.",
            ),
            permission: t(
              "The server rechecks Project membership and technical retain or revise authority.",
            ),
            irreversible: t(
              "Retained summary revisions and controlled outputs are never overwritten or deleted.",
            ),
            failureHandling: t(
              "A failed command changes no summary, receipt or audit row. Retry preserves the same command identity.",
            ),
            audit: t(
              "Actor, reason, request, trace, exact sources, redaction and predecessor are retained.",
            ),
          }}
          onCancel={() => {
            setReviewOpen(false);
          }}
          onConfirm={confirmCommand}
          reasonMaxLength={2000}
          returnFocusTarget={() => returnFocus.current}
          title={t("Review immutable technical summary command")}
        />
      ) : null}
    </section>
  );
}

export default function LiveTrialPage({
  controlledPrintDataSource,
  dataSource,
  formalQualityDataSource,
  navigate,
  projectId,
  reportWorkspaceDirty,
}: {
  controlledPrintDataSource?: ControlledPrintDataSource | undefined;
  dataSource: TrialDataSource;
  formalQualityDataSource?: FormalQualityLinkDataSource | undefined;
  navigate: (target: string) => void;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [detailAttempt, setDetailAttempt] = useState(0);
  const [executionAttempt, setExecutionAttempt] = useState(0);
  const [qualityAttempt, setQualityAttempt] = useState(0);
  const [reviewAttempt, setReviewAttempt] = useState(0);
  const [releasedSummaryAttempt, setReleasedSummaryAttempt] = useState(0);
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [selectedRoundId, setSelectedRoundId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DetailState>({ kind: "idle" });
  const [execution, setExecution] = useState<ExecutionState>({ kind: "idle" });
  const [quality, setQuality] = useState<QualityState>({ kind: "idle" });
  const [review, setReview] = useState<ReviewState>({ kind: "idle" });
  const [releasedSummary, setReleasedSummary] = useState<ReleasedSummaryState>({
    kind: "idle",
  });
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
  const qualityWorkspace = quality.kind === "loaded" ? quality.value : null;
  const reviewWorkspace = review.kind === "loaded" ? review.value : null;
  const selectedRoundTruth =
    reviewWorkspace?.trialRound ??
    qualityWorkspace?.trialRound ??
    executionWorkspace?.round ??
    null;

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
        setQuality(nextRoundId ? { kind: "loading" } : { kind: "idle" });
        setReview(nextRoundId ? { kind: "loading" } : { kind: "idle" });
        setReleasedSummary(
          nextRoundId ? { kind: "loading" } : { kind: "idle" },
        );
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
    if (!selectedRoundId) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadRoundQuality(projectId, selectedRoundId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setQuality({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof TrialRequestCancelledError
        )
          return;
        setQuality({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, projectId, qualityAttempt, selectedRoundId]);

  useEffect(() => {
    if (!selectedRoundId) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadRoundReview(projectId, selectedRoundId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setReview({ kind: "loaded", value });
        setDetail((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  rounds: current.value.rounds.map((round) =>
                    round.globalId === value.trialRound.globalId
                      ? value.trialRound
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
        setReview({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, projectId, reviewAttempt, selectedRoundId]);

  useEffect(() => {
    if (!selectedRoundId) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadReleasedTrialSummaries(projectId, selectedRoundId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setReleasedSummary({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof TrialRequestCancelledError
        )
          return;
        setReleasedSummary({
          kind: "failed",
          failure: toRequestFailure(error),
        });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, projectId, releasedSummaryAttempt, selectedRoundId]);

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
          { id: "trial-live-quality", label: t("Trial quality workspace") },
          { id: "trial-live-review", label: t("Trial review and conclusion") },
          { id: "trial-live-later", label: t("External execution boundary") },
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
      <MobileTrialFieldSummary
        execution={executionWorkspace}
        plan={planDetail}
        projectId={projectId}
        quality={qualityWorkspace}
        round={selectedRoundTruth}
      />
      <MobileEngineeringHandoff />
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
                    setQuality({ kind: "idle" });
                    setReview({ kind: "idle" });
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
                            setQuality({ kind: "loading" });
                            setReview({ kind: "loading" });
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
              <Panel
                className="desktop-engineering-only"
                title={t("Proposed resources")}
              >
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
              <Panel
                className="desktop-engineering-only"
                title={t("Responsible Project members")}
              >
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
              <Panel
                className="desktop-engineering-only"
                title={t("Immutable Plan revision history")}
              >
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
              <Panel
                className="desktop-engineering-only"
                title={t("Planned Rounds")}
              >
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
                                setQuality({ kind: "loading" });
                                setReview({ kind: "loading" });
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
              <Panel
                className="desktop-engineering-only"
                title={t("Generated actions")}
              >
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
              <div id="trial-live-quality" tabIndex={-1} />
              {quality.kind === "loading" ? <LoadingSurface /> : null}
              {quality.kind === "failed" ? (
                <Panel title={t("Trial quality workspace unavailable")}>
                  <RequestFailurePanel failure={quality.failure} />
                  {canRetry(quality.failure) ? (
                    <Button
                      onClick={() => {
                        setQuality({ kind: "loading" });
                        setQualityAttempt((current) => current + 1);
                      }}
                    >
                      {t("Retry")}
                    </Button>
                  ) : null}
                </Panel>
              ) : null}
              {quality.kind === "loaded" ? (
                <TrialQualitySection
                  dataSource={dataSource}
                  execution={executionWorkspace}
                  formalQualityDataSource={formalQualityDataSource}
                  onWorkspace={(value) => {
                    setQuality({ kind: "loaded", value });
                  }}
                  projectId={projectId}
                  reportWorkspaceDirty={reportWorkspaceDirty}
                  workspace={quality.value}
                />
              ) : null}
              <div id="trial-live-review" tabIndex={-1} />
              {review.kind === "loading" ? <LoadingSurface /> : null}
              {review.kind === "failed" ? (
                <Panel title={t("Trial review workspace unavailable")}>
                  <RequestFailurePanel failure={review.failure} />
                  {canRetry(review.failure) ? (
                    <Button
                      onClick={() => {
                        setReview({ kind: "loading" });
                        setReviewAttempt((current) => current + 1);
                      }}
                    >
                      {t("Retry")}
                    </Button>
                  ) : null}
                </Panel>
              ) : null}
              {review.kind === "loaded" ? (
                <TrialReviewSection
                  candidateRounds={planDetail.rounds}
                  dataSource={dataSource}
                  onWorkspace={(value) => {
                    setReview({ kind: "loaded", value });
                    setDetail((current) =>
                      current.kind === "loaded"
                        ? {
                            kind: "loaded",
                            value: {
                              ...current.value,
                              rounds: current.value.rounds.map((round) =>
                                round.globalId === value.trialRound.globalId
                                  ? value.trialRound
                                  : round,
                              ),
                            },
                          }
                        : current,
                    );
                  }}
                  projectId={projectId}
                  reportWorkspaceDirty={reportWorkspaceDirty}
                  workspace={review.value}
                />
              ) : null}
              <div id="trial-live-released-summary" tabIndex={-1} />
              {releasedSummary.kind === "loading" ? <LoadingSurface /> : null}
              {releasedSummary.kind === "failed" ? (
                <Panel title={t("Released Summary workspace unavailable")}>
                  <RequestFailurePanel failure={releasedSummary.failure} />
                  {canRetry(releasedSummary.failure) ? (
                    <Button
                      onClick={() => {
                        setReleasedSummary({ kind: "loading" });
                        setReleasedSummaryAttempt((current) => current + 1);
                      }}
                    >
                      {t("Retry")}
                    </Button>
                  ) : null}
                </Panel>
              ) : null}
              {releasedSummary.kind === "loaded" ? (
                <ReleasedTrialSummarySection
                  controlledPrintDataSource={controlledPrintDataSource}
                  dataSource={dataSource}
                  onWorkspace={(value) => {
                    setReleasedSummary({ kind: "loaded", value });
                  }}
                  projectId={projectId}
                  reportWorkspaceDirty={reportWorkspaceDirty}
                  workspace={releasedSummary.value}
                />
              ) : null}
              <Panel title={t("External execution boundary")}>
                <div
                  className="trial-live__later"
                  id="trial-live-later"
                  tabIndex={-1}
                >
                  <div className="trial-live__later-item">
                    <SemanticStatus
                      label={t("Unavailable in this checkpoint")}
                      tone="neutral"
                    />
                    <span>{t("Formal quality and ERPNext execution")}</span>
                  </div>
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
                  selectedRoundTruth?.displayLabel ?? t("No Round selected"),
                ...(selectedRoundTruth
                  ? { exempt: "identifier" as const }
                  : {}),
              },
              {
                label: t("Round state"),
                value: selectedRoundTruth
                  ? roundStateLabel(t, selectedRoundTruth.currentState)
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
              {
                label: t("Quality defect revisions"),
                value: qualityWorkspace
                  ? formatNumber(
                      locale,
                      qualityWorkspace.defectRevisions.length,
                      0,
                    )
                  : t("Unavailable"),
              },
              {
                label: t("Verification attempts"),
                value: qualityWorkspace
                  ? formatNumber(
                      locale,
                      qualityWorkspace.verificationRevisions.length,
                      0,
                    )
                  : t("Unavailable"),
              },
              {
                label: t("Review policy versions"),
                value: reviewWorkspace
                  ? formatNumber(
                      locale,
                      reviewWorkspace.policyVersions.length,
                      0,
                    )
                  : t("Unavailable"),
              },
              {
                label: t("Review references"),
                value: reviewWorkspace
                  ? formatNumber(
                      locale,
                      latestReviewReferences(reviewWorkspace).length,
                      0,
                    )
                  : t("Unavailable"),
              },
              {
                label: t("Conclusion state"),
                value: reviewWorkspace?.conclusionRevisions.at(-1)
                  ? conclusionStateLabel(
                      t,
                      reviewWorkspace.conclusionRevisions.at(-1)?.state ??
                        "reopened",
                    )
                  : t("Not submitted"),
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
                "P7-04 adds policy-bound comparison, review references, conclusion proposals, independent decisions and reopen history. Gate, readiness, customer signature and formal ERP quality remain unavailable.",
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
