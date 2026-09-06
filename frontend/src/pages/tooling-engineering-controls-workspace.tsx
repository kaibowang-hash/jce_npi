import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
} from "react";

import type {
  CreateToolingCapacityScenarioRevisionCommand,
  CreateToolingDefectRevisionCommand,
  CreateToolingProcessProfileRevisionCommand,
  ToolingCapacityLineInputCommand,
  ToolingCapacityScenarioRevisionViewModel,
  ToolingCockpitViewModel,
  ToolingCommandContext,
  ToolingDataSource,
  ToolingDefectRevisionViewModel,
  ToolingDefectSeverity,
  ToolingDefectState,
  ToolingEngineeringControlsViewModel,
  ToolingProcessMetricCode,
  ToolingRevisionCollectionViewModel,
  ToolingSetCollectionViewModel,
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
import { formatDate, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ResourceState<T> =
  | { kind: "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };
type EditorKind = "defect" | "process" | "capacity";
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

interface WorkspaceResources {
  controls: ToolingEngineeringControlsViewModel;
  revisions: ToolingRevisionCollectionViewModel;
  cockpit: ToolingCockpitViewModel;
  sets: ToolingSetCollectionViewModel;
}

interface DefectDraft {
  defectGlobalId: string;
  expectedVersion: string;
  toolingRevisionGlobalId: string;
  cavityGlobalId: string;
  businessCode: string;
  title: string;
  description: string;
  categoryKey: string;
  severity: ToolingDefectSeverity;
  blocking: boolean;
  state: ToolingDefectState;
  rootCauseState: "pending" | "recorded";
  rootCause: string;
  responsibleMemberGlobalId: string;
  responsibleUserId: string;
  responsibleMemberVersion: string;
  targetRoundLabel: string;
  actionGlobalId: string;
  actionType: "containment" | "corrective" | "preventive";
  actionState: "planned" | "completed" | "verified";
  actionDetail: string;
  actionDueDate: string;
  evidenceRole: "detection" | "analysis" | "action" | "verification";
  fileRevisionGlobalId: string;
  fileOptimisticVersion: string;
  frappeContentHash: string;
  sha256: string;
  reason: string;
}

interface ProcessDraft {
  profileGlobalId: string;
  expectedVersion: string;
  toolingRevisionGlobalId: string;
  effectiveFrom: string;
  metricCode: ToolingProcessMetricCode;
  value: string;
  unit: string;
  minimum: string;
  maximum: string;
  reason: string;
}

interface CapacityLineDraft extends Omit<
  ToolingCapacityLineInputCommand,
  "cavityCount" | "workingDaysPerMonth"
> {
  cavityCount: string;
  key: string;
  partLabel: string;
  workingDaysPerMonth: string;
}

interface CapacityDraft {
  scenarioGlobalId: string;
  expectedVersion: string;
  title: string;
  effectiveFrom: string;
  targetMonthlyAssemblyUnits: string;
  lines: CapacityLineDraft[];
  reason: string;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function LabeledInput({
  label,
  ...properties
}: ComponentProps<typeof TextInput> & { label: string }): React.JSX.Element {
  return (
    <label>
      <span>{label}</span>
      <TextInput {...properties} />
    </label>
  );
}

function latestByStableIdentity<T>(
  values: readonly T[],
  identity: (value: T) => string,
  version: (value: T) => number,
): readonly T[] {
  const latest = new Map<string, T>();
  for (const value of values) {
    const current = latest.get(identity(value));
    if (!current || version(value) > version(current))
      latest.set(identity(value), value);
  }
  return [...latest.values()].sort((left, right) =>
    identity(left).localeCompare(identity(right)),
  );
}

function defectDraft(
  revisions: ToolingRevisionCollectionViewModel | null,
  predecessor: ToolingDefectRevisionViewModel | null,
): DefectDraft {
  const revision =
    revisions?.items.find(
      (item) => item.globalId === predecessor?.toolingRevisionGlobalId,
    ) ?? revisions?.items.at(-1);
  const action = predecessor?.actions[0];
  const evidence = predecessor?.evidence[0];
  return {
    actionDetail: action?.detail ?? "",
    actionDueDate: action?.dueDate ?? today(),
    actionGlobalId: action?.globalId ?? "",
    actionState: action?.state ?? "planned",
    actionType: action?.actionType ?? "corrective",
    blocking: predecessor?.blocking ?? false,
    businessCode: predecessor?.businessCode ?? "",
    categoryKey: predecessor?.categoryKey ?? "",
    cavityGlobalId: predecessor?.cavityGlobalId ?? "",
    defectGlobalId: predecessor?.defectGlobalId ?? "",
    description: predecessor?.description ?? "",
    evidenceRole: evidence?.role ?? "detection",
    expectedVersion: predecessor ? String(predecessor.defectVersion) : "",
    fileOptimisticVersion: evidence
      ? String(evidence.fileOptimisticVersion)
      : "1",
    fileRevisionGlobalId: evidence?.fileRevisionGlobalId ?? "",
    frappeContentHash: evidence?.frappeContentHash ?? "",
    reason: "",
    responsibleMemberGlobalId:
      predecessor?.responsibleMember?.globalId ??
      action?.responsibleMember.globalId ??
      "",
    responsibleMemberVersion: String(
      predecessor?.responsibleMember?.optimisticVersion ??
        action?.responsibleMember.optimisticVersion ??
        1,
    ),
    responsibleUserId:
      predecessor?.responsibleMember?.userId ??
      action?.responsibleMember.userId ??
      "",
    rootCause: predecessor?.rootCause ?? "",
    rootCauseState: predecessor?.rootCauseState ?? "pending",
    severity: predecessor?.severity ?? "medium",
    sha256: evidence?.sha256 ?? "",
    state: predecessor?.state ?? "open",
    targetRoundLabel: predecessor?.targetRoundLabel ?? "",
    title: predecessor?.title ?? "",
    toolingRevisionGlobalId: revision?.globalId ?? "",
  };
}

function processDraft(
  revisions: ToolingRevisionCollectionViewModel | null,
  controls: ToolingEngineeringControlsViewModel | null,
): ProcessDraft {
  const predecessor = controls?.process.customerStandardRevisions.at(-1);
  const revision =
    revisions?.items.find(
      (item) => item.globalId === predecessor?.toolingRevisionGlobalId,
    ) ?? revisions?.items.at(-1);
  const metric = predecessor?.metrics[0];
  return {
    effectiveFrom: predecessor?.effectiveFrom ?? today(),
    expectedVersion: predecessor ? String(predecessor.profileVersion) : "",
    maximum: metric?.comparisonRule?.maximum ?? "",
    metricCode: metric?.code ?? "cycle_time",
    minimum: metric?.comparisonRule?.minimum ?? "",
    profileGlobalId: predecessor?.profileGlobalId ?? "",
    reason: "",
    toolingRevisionGlobalId: revision?.globalId ?? "",
    unit: metric?.unit ?? "s",
    value: metric?.numericValue ?? metric?.textValue ?? "",
  };
}

function initialCapacityLines(
  resources: WorkspaceResources,
): CapacityLineDraft[] {
  const revision = resources.revisions.items.at(-1);
  if (!revision) return [];
  const selectedSet = resources.sets.items[0];
  return resources.cockpit.applicability
    .filter(
      (item) =>
        item.toolingMasterGlobalId === resources.controls.toolingMasterGlobalId,
    )
    .map((item) => ({
      applicabilityGlobalId: item.globalId,
      applicabilitySnapshotHash: item.snapshotHash,
      availableHoursPerDay: "20",
      cavityCount: String(revision.specification.cavityCount),
      cavityProvenance: {
        globalId: revision.globalId,
        kind: "tooling_revision",
        snapshotHash: revision.snapshotHash,
      },
      cycleProvenance: {
        globalId: revision.globalId,
        kind: "tooling_revision",
        snapshotHash: revision.snapshotHash,
      },
      cycleSeconds: revision.specification.targetCycle.value,
      effectiveSetCount: selectedSet ? 1 : 0,
      key: item.globalId,
      oeeRatio: "0.8",
      partLabel:
        resources.cockpit.parts.find(
          (part) => part.currentRevision.globalId === item.part.globalId,
        )?.title ?? item.part.revisionLabel,
      partRevisionGlobalId: item.part.globalId,
      partRevisionSnapshotHash: item.part.snapshotHash,
      selectedToolingSetGlobalIds: selectedSet ? [selectedSet.globalId] : [],
      setProvenance: selectedSet
        ? {
            globalId: selectedSet.globalId,
            kind: "tooling_set_selection",
            snapshotHash: selectedSet.snapshotHash,
          }
        : {
            globalId: null,
            kind: "scenario_assumption",
            snapshotHash: item.snapshotHash,
          },
      usagePerAssembly: "1",
      usageProvenance: {
        globalId: item.globalId,
        kind: "tooling_applicability",
        snapshotHash: item.snapshotHash,
      },
      workingDaysPerMonth: "26",
      yieldRatio: "0.95",
    }));
}

function capacityDraft(
  resources: WorkspaceResources | null,
  predecessor: ToolingCapacityScenarioRevisionViewModel | null,
): CapacityDraft {
  const lines = predecessor
    ? predecessor.lines.map(({ globalId, ...line }) => ({
        ...line,
        cavityCount: String(line.cavityCount),
        key: globalId,
        partLabel:
          resources?.cockpit.parts.find(
            (part) =>
              part.currentRevision.globalId === line.partRevisionGlobalId,
          )?.title ?? line.partRevisionGlobalId.slice(0, 8),
        workingDaysPerMonth: String(line.workingDaysPerMonth),
      }))
    : resources
      ? initialCapacityLines(resources)
      : [];
  return {
    effectiveFrom: predecessor?.effectiveFrom ?? today(),
    expectedVersion: predecessor ? String(predecessor.scenarioVersion) : "",
    lines,
    reason: "",
    scenarioGlobalId: predecessor?.scenarioGlobalId ?? "",
    targetMonthlyAssemblyUnits: predecessor?.targetMonthlyAssemblyUnits ?? "",
    title: predecessor?.title ?? "",
  };
}

function capacityLineCommand(
  line: CapacityLineDraft,
): ToolingCapacityLineInputCommand {
  return {
    applicabilityGlobalId: line.applicabilityGlobalId,
    applicabilitySnapshotHash: line.applicabilitySnapshotHash,
    availableHoursPerDay: line.availableHoursPerDay,
    cavityCount: Number(line.cavityCount),
    cavityProvenance: line.cavityProvenance,
    cycleProvenance: line.cycleProvenance,
    cycleSeconds: line.cycleSeconds,
    effectiveSetCount: line.effectiveSetCount,
    oeeRatio: line.oeeRatio,
    partRevisionGlobalId: line.partRevisionGlobalId,
    partRevisionSnapshotHash: line.partRevisionSnapshotHash,
    selectedToolingSetGlobalIds: line.selectedToolingSetGlobalIds,
    setProvenance: line.setProvenance,
    usagePerAssembly: line.usagePerAssembly,
    usageProvenance: line.usageProvenance,
    workingDaysPerMonth: Number(line.workingDaysPerMonth),
    yieldRatio: line.yieldRatio,
  };
}

function severityLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ToolingDefectSeverity,
): string {
  switch (value) {
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
  value: ToolingDefectState,
): string {
  switch (value) {
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

function metricLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ToolingProcessMetricCode,
): string {
  switch (value) {
    case "cycle_time":
      return t("Cycle time");
    case "part_weight":
      return t("Part weight");
    case "runner_weight":
      return t("Runner weight");
    case "gross_weight_per_cavity":
      return t("Gross weight per cavity");
    case "machine_tonnage":
      return t("Machine tonnage");
    case "machine_type":
      return t("Machine type");
  }
}

export default function ToolingEngineeringControlsWorkspace({
  dataSource,
  masterId,
  projectId,
  reportWorkspaceDirty,
}: {
  dataSource: ToolingDataSource;
  masterId: string;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [resource, setResource] = useState<ResourceState<WorkspaceResources>>({
    kind: "loading",
  });
  const [editor, setEditor] = useState<EditorKind | null>(null);
  const [selectedDefectId, setSelectedDefectId] = useState<string | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(
    null,
  );
  const [defectForm, setDefectForm] = useState<DefectDraft>(() =>
    defectDraft(null, null),
  );
  const [processForm, setProcessForm] = useState<ProcessDraft>(() =>
    processDraft(null, null),
  );
  const [capacityForm, setCapacityForm] = useState<CapacityDraft>(() =>
    capacityDraft(null, null),
  );
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const retryCommand = useRef<(() => void) | null>(null);
  const editorTrigger = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      dataSource.loadEngineeringControls(
        projectId,
        masterId,
        controller.signal,
      ),
      dataSource.loadToolingRevisions(projectId, masterId, controller.signal),
      dataSource.loadMaster(projectId, masterId, controller.signal),
      dataSource.loadSets(projectId, masterId, controller.signal),
    ])
      .then(([controls, revisions, cockpit, sets]) => {
        if (controller.signal.aborted) return;
        const value = { controls, revisions, cockpit, sets };
        setResource({ kind: "loaded", value });
        setSelectedDefectId(
          latestByStableIdentity(
            controls.defectRevisions,
            (item) => item.defectGlobalId,
            (item) => item.defectVersion,
          ).at(-1)?.defectGlobalId ?? null,
        );
        setSelectedScenarioId(
          controls.capacityScenarioRevisions.at(-1)?.scenarioGlobalId ?? null,
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
  }, [attempt, dataSource, masterId, projectId]);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!editor) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: `${masterId}:engineering-controls:${editor}`,
      returnFocusTarget: () => editorTrigger.current,
      version: "unsaved-tooling-engineering-controls",
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [editor, masterId, reportWorkspaceDirty]);

  const loaded = resource.kind === "loaded" ? resource.value : null;
  const latestDefects = useMemo(
    () =>
      latestByStableIdentity(
        loaded?.controls.defectRevisions ?? [],
        (item) => item.defectGlobalId,
        (item) => item.defectVersion,
      ),
    [loaded?.controls.defectRevisions],
  );
  const selectedDefect =
    latestDefects.find((item) => item.defectGlobalId === selectedDefectId) ??
    null;
  const selectedScenario =
    loaded?.controls.capacityScenarioRevisions
      .filter((item) => item.scenarioGlobalId === selectedScenarioId)
      .sort((left, right) => right.scenarioVersion - left.scenarioVersion)[0] ??
    null;
  const latestStandard =
    loaded?.controls.process.customerStandardRevisions.at(-1) ?? null;

  const runCommand = useCallback(
    <T,>(
      label: string,
      prefix: string,
      operation: (context: ToolingCommandContext) => Promise<T>,
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
          .then(() => {
            setEditor(null);
            setFormError(null);
            setCommand({ kind: "idle" });
            setResource({ kind: "loading" });
            setAttempt((current) => current + 1);
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
    [sessionCommandContext],
  );

  const submitDefect = (): void => {
    if (!loaded || !sessionCommandContext) return;
    const revision = loaded.revisions.items.find(
      (item) => item.globalId === defectForm.toolingRevisionGlobalId,
    );
    const memberVersion = Number(defectForm.responsibleMemberVersion);
    const fileVersion = Number(defectForm.fileOptimisticVersion);
    const memberStarted =
      defectForm.responsibleMemberGlobalId.trim() ||
      defectForm.responsibleUserId.trim();
    const evidenceStarted =
      defectForm.fileRevisionGlobalId.trim() ||
      defectForm.frappeContentHash.trim() ||
      defectForm.sha256.trim();
    if (
      !revision ||
      !defectForm.businessCode.trim() ||
      !defectForm.title.trim() ||
      !defectForm.description.trim() ||
      !defectForm.categoryKey.trim() ||
      !defectForm.reason.trim() ||
      (memberStarted &&
        (!defectForm.responsibleMemberGlobalId.trim() ||
          !defectForm.responsibleUserId.trim() ||
          !Number.isInteger(memberVersion) ||
          memberVersion < 1)) ||
      (defectForm.state !== "open" && !memberStarted) ||
      (defectForm.rootCauseState === "recorded" &&
        !defectForm.rootCause.trim()) ||
      (defectForm.actionDetail.trim() && !memberStarted) ||
      (evidenceStarted &&
        (!defectForm.fileRevisionGlobalId.trim() ||
          !defectForm.frappeContentHash.trim() ||
          !defectForm.sha256.trim() ||
          !Number.isInteger(fileVersion) ||
          fileVersion < 1))
    ) {
      setFormError(
        t("Complete the required exact defect and evidence fields."),
      );
      return;
    }
    const responsibleMember = memberStarted
      ? {
          globalId: defectForm.responsibleMemberGlobalId.trim(),
          optimisticVersion: memberVersion,
          userId: defectForm.responsibleUserId.trim(),
        }
      : null;
    const command: CreateToolingDefectRevisionCommand = {
      ...(defectForm.defectGlobalId
        ? {
            defectGlobalId: defectForm.defectGlobalId,
            expectedVersion: Number(defectForm.expectedVersion),
          }
        : {}),
      actions:
        defectForm.actionDetail.trim() && responsibleMember
          ? [
              {
                ...(defectForm.actionGlobalId
                  ? { globalId: defectForm.actionGlobalId }
                  : {}),
                actionType: defectForm.actionType,
                detail: defectForm.actionDetail.trim(),
                dueDate: defectForm.actionDueDate,
                evidence: [],
                responsibleMember,
                state: defectForm.actionState,
              },
            ]
          : [],
      blocking: defectForm.blocking,
      businessCode: defectForm.businessCode.trim(),
      categoryKey: defectForm.categoryKey.trim(),
      cavityGlobalId: defectForm.cavityGlobalId || null,
      description: defectForm.description.trim(),
      detectionContext: {
        globalId: revision.globalId,
        kind: "tooling_revision",
        snapshotHash: revision.snapshotHash,
      },
      evidence: evidenceStarted
        ? [
            {
              fileOptimisticVersion: fileVersion,
              fileRevisionGlobalId: defectForm.fileRevisionGlobalId.trim(),
              frappeContentHash: defectForm.frappeContentHash.trim(),
              role: defectForm.evidenceRole,
              sha256: defectForm.sha256.trim(),
            },
          ]
        : [],
      reason: defectForm.reason.trim(),
      responsibleMember,
      rootCause:
        defectForm.rootCauseState === "recorded"
          ? defectForm.rootCause.trim()
          : null,
      rootCauseState: defectForm.rootCauseState,
      severity: defectForm.severity,
      state: defectForm.state,
      targetRoundLabel: defectForm.targetRoundLabel.trim() || null,
      title: defectForm.title.trim(),
      toolingRevisionGlobalId: revision.globalId,
      toolingRevisionSnapshotHash: revision.snapshotHash,
    };
    runCommand(
      t("Appending immutable defect Revision"),
      "tooling-defect",
      (context) =>
        dataSource.createToolingDefectRevision(
          projectId,
          masterId,
          command,
          context,
        ),
    );
  };

  const submitProcess = (): void => {
    if (!loaded || !sessionCommandContext) return;
    const revision = loaded.revisions.items.find(
      (item) => item.globalId === processForm.toolingRevisionGlobalId,
    );
    const numeric = processForm.metricCode !== "machine_type";
    const comparisonStarted =
      processForm.minimum.trim() || processForm.maximum.trim();
    if (
      !revision ||
      !processForm.value.trim() ||
      (numeric && !processForm.unit.trim()) ||
      !processForm.reason.trim() ||
      (comparisonStarted &&
        (!processForm.minimum.trim() || !processForm.maximum.trim()))
    ) {
      setFormError(
        t("Complete the Customer Standard value, source and reason."),
      );
      return;
    }
    const command: CreateToolingProcessProfileRevisionCommand = {
      ...(processForm.profileGlobalId
        ? {
            expectedVersion: Number(processForm.expectedVersion),
            profileGlobalId: processForm.profileGlobalId,
          }
        : {}),
      context: {
        globalId: revision.globalId,
        kind: "tooling_revision_specification",
        snapshotHash: revision.snapshotHash,
      },
      effectiveFrom: processForm.effectiveFrom,
      metrics: [
        {
          code: processForm.metricCode,
          comparisonRule:
            numeric && comparisonStarted
              ? {
                  maximum: processForm.maximum.trim(),
                  minimum: processForm.minimum.trim(),
                  unit: processForm.unit.trim(),
                }
              : null,
          numericValue: numeric ? processForm.value.trim() : null,
          textValue: numeric ? null : processForm.value.trim(),
          unit: numeric ? processForm.unit.trim() : null,
          valueKind: numeric ? "numeric" : "text",
        },
      ],
      reason: processForm.reason.trim(),
      toolingRevisionGlobalId: revision.globalId,
      toolingRevisionSnapshotHash: revision.snapshotHash,
    };
    runCommand(
      t("Appending Customer Standard process profile"),
      "tooling-process-profile",
      (context) =>
        dataSource.createToolingProcessProfileRevision(
          projectId,
          masterId,
          command,
          context,
        ),
    );
  };

  const submitCapacity = (): void => {
    if (!loaded || !sessionCommandContext) return;
    const validLines = capacityForm.lines.every(
      (line) =>
        Number(line.availableHoursPerDay) > 0 &&
        Number.isInteger(Number(line.workingDaysPerMonth)) &&
        Number(line.workingDaysPerMonth) >= 1 &&
        Number(line.workingDaysPerMonth) <= 31 &&
        Number(line.oeeRatio) >= 0 &&
        Number(line.oeeRatio) <= 1 &&
        Number(line.yieldRatio) >= 0 &&
        Number(line.yieldRatio) <= 1 &&
        Number(line.cycleSeconds) > 0 &&
        Number.isInteger(Number(line.cavityCount)) &&
        Number(line.cavityCount) >= 1 &&
        Number(line.usagePerAssembly) > 0,
    );
    if (
      !capacityForm.title.trim() ||
      !capacityForm.targetMonthlyAssemblyUnits.trim() ||
      Number(capacityForm.targetMonthlyAssemblyUnits) < 0 ||
      capacityForm.lines.length === 0 ||
      !validLines ||
      !capacityForm.reason.trim()
    ) {
      setFormError(t("Complete every explicit capacity input and reason."));
      return;
    }
    const command: CreateToolingCapacityScenarioRevisionCommand = {
      ...(capacityForm.scenarioGlobalId
        ? {
            expectedVersion: Number(capacityForm.expectedVersion),
            scenarioGlobalId: capacityForm.scenarioGlobalId,
          }
        : {}),
      effectiveFrom: capacityForm.effectiveFrom,
      lines: capacityForm.lines.map(capacityLineCommand),
      reason: capacityForm.reason.trim(),
      targetMonthlyAssemblyUnits:
        capacityForm.targetMonthlyAssemblyUnits.trim(),
      title: capacityForm.title.trim(),
    };
    runCommand(
      t("Appending immutable Capacity Scenario Revision"),
      "tooling-capacity",
      (context) =>
        dataSource.createToolingCapacityScenarioRevision(
          projectId,
          masterId,
          command,
          context,
        ),
    );
  };

  if (resource.kind === "failed") {
    return (
      <Panel
        id="tooling-engineering-controls-workspace"
        title={t("Engineering controls workspace")}
      >
        <RequestFailurePanel failure={resource.failure} />
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
      </Panel>
    );
  }

  if (resource.kind === "loading" || !loaded) {
    return (
      <Panel
        id="tooling-engineering-controls-workspace"
        title={t("Engineering controls workspace")}
      >
        <p aria-busy="true" role="status">
          {t("Loading engineering controls workspace")}
        </p>
      </Panel>
    );
  }

  const processing = command.kind === "processing";
  const openBlockingCount = latestDefects.filter(
    (item) => item.blocking && item.state !== "closed",
  ).length;
  const canDefect =
    loaded.controls.permissions.reviseDefect &&
    sessionCommandContext !== null &&
    loaded.revisions.items.length > 0;
  const canProcess =
    loaded.controls.permissions.createCustomerStandard &&
    sessionCommandContext !== null &&
    loaded.revisions.items.length > 0;
  const canCapacity =
    loaded.controls.permissions.createCapacityScenario &&
    sessionCommandContext !== null &&
    initialCapacityLines(loaded).length > 0;

  const openEditor = (kind: EditorKind, trigger: HTMLElement): void => {
    editorTrigger.current = trigger;
    setFormError(null);
    setEditor(kind);
    if (kind === "defect")
      setDefectForm(defectDraft(loaded.revisions, selectedDefect));
    if (kind === "process")
      setProcessForm(processDraft(loaded.revisions, loaded.controls));
    if (kind === "capacity")
      setCapacityForm(capacityDraft(loaded, selectedScenario));
  };

  return (
    <Panel
      id="tooling-engineering-controls-workspace"
      title={t("Engineering controls workspace")}
    >
      <div className="tooling-set__toolbar">
        <div>
          <SemanticStatus
            label={
              openBlockingCount > 0
                ? t("Open blocking intent")
                : t("No open blocking intent")
            }
            tone={openBlockingCount > 0 ? "warning" : "neutral"}
          />
          <span>
            {t("Current Tooling defects")}:{" "}
            {formatNumber(locale, latestDefects.length, 0)}
            {" · "}
            {t("Open blocking count")}:{" "}
            {formatNumber(locale, openBlockingCount, 0)}
          </span>
        </div>
        <div className="tooling-engineering__actions">
          {loaded.controls.permissions.reviseDefect && !editor ? (
            <Button
              disabled={!canDefect || processing}
              onClick={(event) => {
                openEditor("defect", event.currentTarget);
              }}
              visual="primary"
            >
              {selectedDefect
                ? t("Append defect Revision")
                : t("Create Tooling defect")}
            </Button>
          ) : null}
          {loaded.controls.permissions.createCustomerStandard && !editor ? (
            <Button
              disabled={!canProcess || processing}
              onClick={(event) => {
                openEditor("process", event.currentTarget);
              }}
            >
              {latestStandard
                ? t("Append Customer Standard Revision")
                : t("Create Customer Standard")}
            </Button>
          ) : null}
          {loaded.controls.permissions.createCapacityScenario && !editor ? (
            <Button
              disabled={!canCapacity || processing}
              onClick={(event) => {
                openEditor("capacity", event.currentTarget);
              }}
            >
              {selectedScenario
                ? t("Append Capacity Scenario Revision")
                : t("Create Capacity Scenario")}
            </Button>
          ) : null}
        </div>
      </div>

      {!sessionCommandContext &&
      (loaded.controls.permissions.reviseDefect ||
        loaded.controls.permissions.createCustomerStandard ||
        loaded.controls.permissions.createCapacityScenario) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>
            {t("Engineering controls are read only in this session.")}
          </span>
          <span>
            {t(
              "Session verification is required before an engineering command can be submitted.",
            )}
          </span>
        </div>
      ) : null}
      {!loaded.controls.permissions.reviseDefect &&
      !loaded.controls.permissions.createCustomerStandard &&
      !loaded.controls.permissions.createCapacityScenario ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>
            {t("Engineering controls are read only for this account.")}
          </span>
          <span>{t("The server controls every append capability.")}</span>
        </div>
      ) : null}
      {command.kind === "processing" ? (
        <div
          aria-busy="true"
          className="scenario-banner scenario-banner--processing"
          role="status"
        >
          <span>{command.label}</span>
          <span>{t("The immutable command is processing.")}</span>
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

      <section
        aria-label={t("Tooling defect control")}
        className="tooling-engineering__section"
      >
        <div className="tooling-set__toolbar">
          <div>
            <strong>{t("Tooling defect control")}</strong>
            <span>
              {t("Severity and blocking intent are independent facts.")}
            </span>
          </div>
        </div>
        {latestDefects.length === 0 ? (
          <div className="empty-state" role="status">
            <strong>{t("No Tooling defect has been recorded.")}</strong>
            <span>
              {t(
                "No Gate blocker or Trial result is inferred from an empty history.",
              )}
            </span>
          </div>
        ) : (
          <div className="tooling-engineering__layout">
            <div className="table-scroll" tabIndex={0}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("Tooling Defect Code")}</th>
                    <th>{t("Tooling Defect State")}</th>
                    <th>{t("Tooling Defect Severity")}</th>
                    <th>{t("Blocking intent")}</th>
                    <th>{t("Location")}</th>
                    <th>{t("Actions")}</th>
                    <th>{t("Evidence")}</th>
                  </tr>
                </thead>
                <tbody>
                  {latestDefects.map((item) => (
                    <tr
                      aria-selected={item.defectGlobalId === selectedDefectId}
                      key={item.globalId}
                    >
                      <td>
                        <button
                          className="table-link"
                          onClick={() => {
                            setSelectedDefectId(item.defectGlobalId);
                          }}
                          type="button"
                        >
                          <span data-language-exempt="business-data">
                            {item.businessCode}
                          </span>{" "}
                          · {formatNumber(locale, item.defectVersion, 0)}
                        </button>
                      </td>
                      <td>
                        <SemanticStatus
                          label={defectStateLabel(t, item.state)}
                          tone={item.state === "closed" ? "success" : "info"}
                        />
                      </td>
                      <td>{severityLabel(t, item.severity)}</td>
                      <td>
                        {item.blocking
                          ? t("Explicitly blocking")
                          : t("Not blocking")}
                      </td>
                      <td>
                        {item.cavityIdentifier ? (
                          <span data-language-exempt="business-data">
                            {item.cavityIdentifier}
                          </span>
                        ) : (
                          t("Whole Tooling Revision")
                        )}
                      </td>
                      <td>{formatNumber(locale, item.actions.length, 0)}</td>
                      <td>{formatNumber(locale, item.evidence.length, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <aside
              aria-label={t("Defect lineage inspector")}
              className="tooling-set__inspector"
            >
              {selectedDefect ? (
                <>
                  <DefinitionList
                    rows={[
                      {
                        exempt: "business-data",
                        label: t("Tooling Defect Title"),
                        value: selectedDefect.title,
                      },
                      {
                        exempt: "business-data",
                        label: t("Responsible member"),
                        value:
                          selectedDefect.responsibleMember?.userId ??
                          t("Unassigned"),
                      },
                      {
                        exempt: "business-data",
                        label: t("Target-round intention"),
                        value:
                          selectedDefect.targetRoundLabel ?? t("Not recorded"),
                      },
                      {
                        exempt: "identifier",
                        label: t("Predecessor Revision"),
                        value:
                          selectedDefect.predecessorGlobalId ??
                          t("Initial Revision"),
                      },
                    ]}
                  />
                  <small>
                    {t(
                      "The target-round label is planning intent, not a Trial identity.",
                    )}
                  </small>
                  <strong>{t("Defect actions")}</strong>
                  {selectedDefect.actions.length ? (
                    <ul className="tooling-engineering__plain-list">
                      {selectedDefect.actions.map((action) => (
                        <li key={action.globalId}>
                          <span data-language-exempt="business-data">
                            {action.detail}
                          </span>
                          <span>{formatDate(locale, action.dueDate)} · </span>
                          <span data-language-exempt="business-data">
                            {action.responsibleMember.userId}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <span>{t("No action is recorded.")}</span>
                  )}
                </>
              ) : null}
            </aside>
          </div>
        )}
      </section>

      <section
        aria-label={t("Process fact comparison")}
        className="tooling-engineering__section"
      >
        <strong>{t("Process fact comparison")}</strong>
        <div className="tooling-engineering__process-grid">
          <article>
            <span>{t("Customer Standard")}</span>
            <SemanticStatus
              label={latestStandard ? t("Available") : t("Empty")}
              tone={latestStandard ? "info" : "neutral"}
            />
            {latestStandard ? (
              <dl>
                {latestStandard.metrics.map((metric) => (
                  <div key={metric.globalId}>
                    <dt>{metricLabel(t, metric.code)}</dt>
                    <dd data-language-exempt="business-data">
                      {metric.numericValue ?? metric.textValue}{" "}
                      <span data-language-exempt="unit">{metric.unit}</span>
                    </dd>
                  </div>
                ))}
              </dl>
            ) : (
              <span>{t("No Customer Standard is recorded.")}</span>
            )}
          </article>
          <article>
            <span>{t("Trial Actual")}</span>
            <SemanticStatus label={t("Not measured")} tone="neutral" />
            <span>
              {t("An exact Trial context is unavailable until Phase 7.")}
            </span>
          </article>
          <article>
            <span>{t("Approved Process Baseline")}</span>
            <SemanticStatus label={t("Unavailable")} tone="neutral" />
            <span>
              {t("Approved Trial evidence is unavailable until Phase 7.")}
            </span>
          </article>
        </div>
        {loaded.controls.process.comparisons.length ? (
          <div className="table-scroll" tabIndex={0}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("Metric")}</th>
                  <th>{t("Reference")}</th>
                  <th>{t("Actual")}</th>
                  <th>{t("Comparison state")}</th>
                  <th>{t("Tolerance rule")}</th>
                </tr>
              </thead>
              <tbody>
                {loaded.controls.process.comparisons.map((item) => (
                  <tr key={`${item.referenceLayer}-${item.metricCode}`}>
                    <td>{metricLabel(t, item.metricCode)}</td>
                    <td data-language-exempt="business-data">
                      {item.referenceValue ?? t("Unavailable")}
                    </td>
                    <td data-language-exempt="business-data">
                      {item.actualValue ?? t("Not measured")}
                    </td>
                    <td>
                      <SemanticStatus
                        label={
                          item.state === "not_measured"
                            ? t("Not measured")
                            : item.state === "within_tolerance"
                              ? t("Within tolerance")
                              : item.state === "outside_tolerance"
                                ? t("Outside tolerance")
                                : t("Unavailable")
                        }
                        tone="neutral"
                      />
                    </td>
                    <td data-language-exempt="identifier">
                      {item.ruleGlobalId ?? t("No exact rule")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section
        aria-label={t("Capacity Scenario planning")}
        className="tooling-engineering__section"
      >
        <div className="tooling-set__toolbar">
          <div>
            <strong>{t("Capacity Scenario planning")}</strong>
            <span>
              <span data-language-exempt="identifier">capacity.v1</span> ·{" "}
              <span data-language-exempt="identifier">decimal-6-half-even</span>
            </span>
          </div>
        </div>
        {loaded.controls.capacityScenarioRevisions.length === 0 ? (
          <div className="empty-state" role="status">
            <strong>{t("No Capacity Scenario has been recorded.")}</strong>
            <span>
              {t("No capacity or zero gap is inferred from an empty history.")}
            </span>
          </div>
        ) : (
          <div className="tooling-engineering__layout">
            <div className="table-scroll" tabIndex={0}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("Capacity Scenario Title")}</th>
                    <th>{t("Capacity Scenario Version")}</th>
                    <th>{t("Part lines")}</th>
                    <th>{t("Assembly units per month")}</th>
                    <th>{t("Capacity gap")}</th>
                  </tr>
                </thead>
                <tbody>
                  {loaded.controls.capacityScenarioRevisions.map((item) => (
                    <tr
                      aria-selected={
                        item.scenarioGlobalId === selectedScenarioId
                      }
                      key={item.globalId}
                    >
                      <td>
                        <button
                          className="table-link"
                          onClick={() => {
                            setSelectedScenarioId(item.scenarioGlobalId);
                          }}
                          type="button"
                        >
                          <span data-language-exempt="business-data">
                            {item.title}
                          </span>
                        </button>
                      </td>
                      <td>{formatNumber(locale, item.scenarioVersion, 0)}</td>
                      <td>{formatNumber(locale, item.lines.length, 0)}</td>
                      <td data-language-exempt="business-data">
                        {item.result.scenarioAssemblyUnitsPerMonth}
                      </td>
                      <td data-language-exempt="business-data">
                        {item.result.gap}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <aside
              aria-label={t("Capacity result inspector")}
              className="tooling-set__inspector"
            >
              {selectedScenario ? (
                <DefinitionList
                  rows={[
                    {
                      exempt: "business-data",
                      label: t("Target monthly assembly units"),
                      value: selectedScenario.targetMonthlyAssemblyUnits,
                    },
                    {
                      exempt: "business-data",
                      label: t("Scenario monthly capacity"),
                      value:
                        selectedScenario.result.scenarioAssemblyUnitsPerMonth,
                    },
                    {
                      exempt: "business-data",
                      label: t("Capacity gap"),
                      value: selectedScenario.result.gap,
                    },
                    {
                      label: t("Bottleneck lines"),
                      value: formatNumber(
                        locale,
                        selectedScenario.result.bottleneckLineGlobalIds.length,
                        0,
                      ),
                    },
                  ]}
                />
              ) : null}
            </aside>
          </div>
        )}
        {selectedScenario ? (
          <div className="table-scroll" tabIndex={0}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("Part Revision")}</th>
                  <th>{t("Hours per day")}</th>
                  <th>{t("Working days")}</th>
                  <th>{t("OEE")}</th>
                  <th>{t("Yield")}</th>
                  <th>{t("Cycle seconds")}</th>
                  <th>{t("Cavities")}</th>
                  <th>{t("Effective Sets")}</th>
                  <th>{t("Assembly units per month")}</th>
                  <th>{t("Bottleneck")}</th>
                </tr>
              </thead>
              <tbody>
                {selectedScenario.lines.map((line, index) => {
                  const result = selectedScenario.result.lineResults[index];
                  return (
                    <tr key={line.globalId}>
                      <td data-language-exempt="identifier">
                        {line.partRevisionGlobalId.slice(0, 8)}
                      </td>
                      <td data-language-exempt="business-data">
                        {line.availableHoursPerDay}
                      </td>
                      <td>
                        {formatNumber(locale, line.workingDaysPerMonth, 0)}
                      </td>
                      <td data-language-exempt="business-data">
                        {line.oeeRatio}
                      </td>
                      <td data-language-exempt="business-data">
                        {line.yieldRatio}
                      </td>
                      <td data-language-exempt="business-data">
                        {line.cycleSeconds}
                      </td>
                      <td>{formatNumber(locale, line.cavityCount, 0)}</td>
                      <td>{formatNumber(locale, line.effectiveSetCount, 0)}</td>
                      <td data-language-exempt="business-data">
                        {result?.assemblyUnitsPerMonth ?? t("Unavailable")}
                      </td>
                      <td>
                        {selectedScenario.result.bottleneckLineGlobalIds.includes(
                          line.globalId,
                        )
                          ? t("Bottleneck")
                          : t("Not bottleneck")}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section
        aria-label={t("ERP and IoT Tooling health")}
        className="tooling-engineering__section"
      >
        <strong>{t("ERP and IoT Tooling health")}</strong>
        <div className="tooling-engineering__health-grid">
          {(
            [
              [t("Shot count"), loaded.controls.health.shotCount],
              [t("Shot-count calibration"), loaded.controls.health.calibration],
              [t("Maintenance projection"), loaded.controls.health.maintenance],
              [t("Tooling health score"), loaded.controls.health.healthScore],
            ] as const
          ).map(([label, value]) => (
            <article key={label}>
              <span>{label}</span>
              <SemanticStatus label={t("Unavailable")} tone="neutral" />
              <span data-language-exempt="business-data">
                {value.reasonCode}
              </span>
            </article>
          ))}
        </div>
        <small>
          {t(
            "No shot count, calibration result, maintenance state, health score or recommendation is inferred.",
          )}
        </small>
      </section>

      {editor === "defect" ? (
        <form
          className="tooling-engineering__form"
          onSubmit={(event) => {
            event.preventDefault();
            submitDefect();
          }}
        >
          <h3>
            {defectForm.defectGlobalId
              ? t("Append immutable Tooling defect Revision")
              : t("Create immutable Tooling defect")}
          </h3>
          <div className="form-grid form-grid--two">
            <label>
              <span>{t("Tooling Revision")}</span>
              <Select
                onChange={(event) => {
                  setDefectForm((current) => ({
                    ...current,
                    toolingRevisionGlobalId: event.target.value,
                  }));
                }}
                value={defectForm.toolingRevisionGlobalId}
              >
                {loaded.revisions.items.map((item) => (
                  <option key={item.globalId} value={item.globalId}>
                    {item.revisionLabel}
                  </option>
                ))}
              </Select>
            </label>
            <label>
              <span>{t("Cavity")}</span>
              <Select
                onChange={(event) => {
                  setDefectForm((current) => ({
                    ...current,
                    cavityGlobalId: event.target.value,
                  }));
                }}
                value={defectForm.cavityGlobalId}
              >
                <option value="">{t("Whole Tooling Revision")}</option>
                {loaded.revisions.items
                  .find(
                    (item) =>
                      item.globalId === defectForm.toolingRevisionGlobalId,
                  )
                  ?.cavities.map((item) => (
                    <option key={item.globalId} value={item.globalId}>
                      {item.cavityIdentifier}
                    </option>
                  ))}
              </Select>
            </label>
            <LabeledInput
              label={t("Tooling Defect Code")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  businessCode: event.target.value,
                }));
              }}
              value={defectForm.businessCode}
            />
            <LabeledInput
              label={t("Tooling Defect Title")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  title: event.target.value,
                }));
              }}
              value={defectForm.title}
            />
            <label>
              <span>{t("Tooling Defect Severity")}</span>
              <Select
                onChange={(event) => {
                  setDefectForm((current) => ({
                    ...current,
                    severity: event.target.value as ToolingDefectSeverity,
                  }));
                }}
                value={defectForm.severity}
              >
                {(["low", "medium", "high", "critical"] as const).map(
                  (item) => (
                    <option key={item} value={item}>
                      {severityLabel(t, item)}
                    </option>
                  ),
                )}
              </Select>
            </label>
            <label>
              <span>{t("Tooling Defect State")}</span>
              <Select
                onChange={(event) => {
                  setDefectForm((current) => ({
                    ...current,
                    state: event.target.value as ToolingDefectState,
                  }));
                }}
                value={defectForm.state}
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
                ).map((item) => (
                  <option key={item} value={item}>
                    {defectStateLabel(t, item)}
                  </option>
                ))}
              </Select>
            </label>
            <LabeledInput
              label={t("Tooling Defect Category Key")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  categoryKey: event.target.value,
                }));
              }}
              value={defectForm.categoryKey}
            />
            <label className="checkbox-field">
              <input
                checked={defectForm.blocking}
                onChange={(event) => {
                  setDefectForm((current) => ({
                    ...current,
                    blocking: event.target.checked,
                  }));
                }}
                type="checkbox"
              />
              <span>{t("Explicit blocking intent")}</span>
            </label>
            <LabeledInput
              label={t("Responsible member Global ID")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  responsibleMemberGlobalId: event.target.value,
                }));
              }}
              value={defectForm.responsibleMemberGlobalId}
            />
            <LabeledInput
              label={t("Responsible user ID")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  responsibleUserId: event.target.value,
                }));
              }}
              value={defectForm.responsibleUserId}
            />
            <LabeledInput
              label={t("Responsible member version")}
              min="1"
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  responsibleMemberVersion: event.target.value,
                }));
              }}
              type="number"
              value={defectForm.responsibleMemberVersion}
            />
            <LabeledInput
              label={t("Target-round intention")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  targetRoundLabel: event.target.value,
                }));
              }}
              value={defectForm.targetRoundLabel}
            />
            <LabeledInput
              label={t("Corrective action")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  actionDetail: event.target.value,
                }));
              }}
              value={defectForm.actionDetail}
            />
            <LabeledInput
              label={t("Action due date")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  actionDueDate: event.target.value,
                }));
              }}
              type="date"
              value={defectForm.actionDueDate}
            />
            <LabeledInput
              label={t("File Revision Global ID")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  fileRevisionGlobalId: event.target.value,
                }));
              }}
              value={defectForm.fileRevisionGlobalId}
            />
            <LabeledInput
              label={t("File optimistic version")}
              min="1"
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  fileOptimisticVersion: event.target.value,
                }));
              }}
              type="number"
              value={defectForm.fileOptimisticVersion}
            />
            <LabeledInput
              label={t("Frappe content hash")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  frappeContentHash: event.target.value,
                }));
              }}
              value={defectForm.frappeContentHash}
            />
            <LabeledInput
              label={t("SHA-256")}
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  sha256: event.target.value,
                }));
              }}
              value={defectForm.sha256}
            />
          </div>
          <label>
            <span>{t("Tooling Defect Description")}</span>
            <textarea
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  description: event.target.value,
                }));
              }}
              value={defectForm.description}
            />
          </label>
          <label>
            <span>{t("Root cause")}</span>
            <textarea
              onChange={(event) => {
                setDefectForm((current) => ({
                  ...current,
                  rootCause: event.target.value,
                  rootCauseState: event.target.value.trim()
                    ? "recorded"
                    : "pending",
                }));
              }}
              value={defectForm.rootCause}
            />
          </label>
          <LabeledInput
            label={t("Tooling Defect Revision Reason")}
            onChange={(event) => {
              setDefectForm((current) => ({
                ...current,
                reason: event.target.value,
              }));
            }}
            value={defectForm.reason}
          />
          {formError ? (
            <p className="form-error" role="alert">
              {formError}
            </p>
          ) : null}
          <div className="form-actions">
            <Button disabled={processing} type="submit" visual="primary">
              {t("Append immutable defect Revision")}
            </Button>
            <Button
              disabled={processing}
              onClick={() => {
                setEditor(null);
              }}
              type="button"
            >
              {t("Cancel")}
            </Button>
          </div>
        </form>
      ) : null}

      {editor === "process" ? (
        <form
          className="tooling-engineering__form"
          onSubmit={(event) => {
            event.preventDefault();
            submitProcess();
          }}
        >
          <h3>{t("Append Customer Standard process profile")}</h3>
          <div className="form-grid form-grid--two">
            <label>
              <span>{t("Tooling Revision")}</span>
              <Select
                onChange={(event) => {
                  setProcessForm((current) => ({
                    ...current,
                    toolingRevisionGlobalId: event.target.value,
                  }));
                }}
                value={processForm.toolingRevisionGlobalId}
              >
                {loaded.revisions.items.map((item) => (
                  <option key={item.globalId} value={item.globalId}>
                    {item.revisionLabel}
                  </option>
                ))}
              </Select>
            </label>
            <label>
              <span>{t("Process metric")}</span>
              <Select
                onChange={(event) => {
                  setProcessForm((current) => ({
                    ...current,
                    metricCode: event.target.value as ToolingProcessMetricCode,
                    unit:
                      event.target.value === "machine_type" ? "" : current.unit,
                  }));
                }}
                value={processForm.metricCode}
              >
                {(
                  [
                    "cycle_time",
                    "part_weight",
                    "runner_weight",
                    "gross_weight_per_cavity",
                    "machine_tonnage",
                    "machine_type",
                  ] as const
                ).map((item) => (
                  <option key={item} value={item}>
                    {metricLabel(t, item)}
                  </option>
                ))}
              </Select>
            </label>
            <LabeledInput
              label={t("Customer Standard value")}
              onChange={(event) => {
                setProcessForm((current) => ({
                  ...current,
                  value: event.target.value,
                }));
              }}
              value={processForm.value}
            />
            <LabeledInput
              disabled={processForm.metricCode === "machine_type"}
              label={t("Unit")}
              onChange={(event) => {
                setProcessForm((current) => ({
                  ...current,
                  unit: event.target.value,
                }));
              }}
              value={processForm.unit}
            />
            <LabeledInput
              disabled={processForm.metricCode === "machine_type"}
              label={t("Tolerance minimum")}
              onChange={(event) => {
                setProcessForm((current) => ({
                  ...current,
                  minimum: event.target.value,
                }));
              }}
              value={processForm.minimum}
            />
            <LabeledInput
              disabled={processForm.metricCode === "machine_type"}
              label={t("Tolerance maximum")}
              onChange={(event) => {
                setProcessForm((current) => ({
                  ...current,
                  maximum: event.target.value,
                }));
              }}
              value={processForm.maximum}
            />
            <LabeledInput
              label={t("Effective from")}
              onChange={(event) => {
                setProcessForm((current) => ({
                  ...current,
                  effectiveFrom: event.target.value,
                }));
              }}
              type="date"
              value={processForm.effectiveFrom}
            />
            <LabeledInput
              label={t("Process Profile Revision Reason")}
              onChange={(event) => {
                setProcessForm((current) => ({
                  ...current,
                  reason: event.target.value,
                }));
              }}
              value={processForm.reason}
            />
          </div>
          {formError ? (
            <p className="form-error" role="alert">
              {formError}
            </p>
          ) : null}
          <div className="form-actions">
            <Button disabled={processing} type="submit" visual="primary">
              {t("Append Customer Standard Revision")}
            </Button>
            <Button
              disabled={processing}
              onClick={() => {
                setEditor(null);
              }}
              type="button"
            >
              {t("Cancel")}
            </Button>
          </div>
        </form>
      ) : null}

      {editor === "capacity" ? (
        <form
          className="tooling-engineering__form"
          onSubmit={(event) => {
            event.preventDefault();
            submitCapacity();
          }}
        >
          <h3>{t("Append immutable Capacity Scenario Revision")}</h3>
          <div className="form-grid form-grid--two">
            <LabeledInput
              label={t("Capacity Scenario Title")}
              onChange={(event) => {
                setCapacityForm((current) => ({
                  ...current,
                  title: event.target.value,
                }));
              }}
              value={capacityForm.title}
            />
            <LabeledInput
              label={t("Target monthly assembly units")}
              min="0"
              onChange={(event) => {
                setCapacityForm((current) => ({
                  ...current,
                  targetMonthlyAssemblyUnits: event.target.value,
                }));
              }}
              step="any"
              type="number"
              value={capacityForm.targetMonthlyAssemblyUnits}
            />
            <LabeledInput
              label={t("Effective from")}
              onChange={(event) => {
                setCapacityForm((current) => ({
                  ...current,
                  effectiveFrom: event.target.value,
                }));
              }}
              type="date"
              value={capacityForm.effectiveFrom}
            />
            <LabeledInput
              label={t("Capacity Scenario Revision Reason")}
              onChange={(event) => {
                setCapacityForm((current) => ({
                  ...current,
                  reason: event.target.value,
                }));
              }}
              value={capacityForm.reason}
            />
          </div>
          <fieldset className="tooling-engineering__capacity-lines">
            <legend>{t("Explicit Part capacity inputs")}</legend>
            {capacityForm.lines.map((line, index) => (
              <div
                className="tooling-engineering__capacity-line"
                key={line.key}
              >
                <strong data-language-exempt="business-data">
                  {line.partLabel}
                </strong>
                {(
                  [
                    ["availableHoursPerDay", t("Hours per day")],
                    ["workingDaysPerMonth", t("Working days")],
                    ["oeeRatio", t("OEE")],
                    ["yieldRatio", t("Yield")],
                    ["cycleSeconds", t("Cycle seconds")],
                    ["cavityCount", t("Cavities")],
                    ["usagePerAssembly", t("Usage per assembly")],
                  ] as const
                ).map(([field, label]) => (
                  <LabeledInput
                    key={field}
                    label={label}
                    min="0"
                    onChange={(event) => {
                      setCapacityForm((current) => ({
                        ...current,
                        lines: current.lines.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, [field]: event.target.value }
                            : item,
                        ),
                      }));
                    }}
                    step={
                      field === "workingDaysPerMonth" || field === "cavityCount"
                        ? "1"
                        : "any"
                    }
                    type="number"
                    value={line[field]}
                  />
                ))}
                <span>
                  {t("Selected exact Tooling Sets")}:{" "}
                  {formatNumber(
                    locale,
                    line.selectedToolingSetGlobalIds.length,
                    0,
                  )}
                </span>
              </div>
            ))}
          </fieldset>
          {formError ? (
            <p className="form-error" role="alert">
              {formError}
            </p>
          ) : null}
          <div className="form-actions">
            <Button disabled={processing} type="submit" visual="primary">
              {t("Append Capacity Scenario Revision")}
            </Button>
            <Button
              disabled={processing}
              onClick={() => {
                setEditor(null);
              }}
              type="button"
            >
              {t("Cancel")}
            </Button>
          </div>
        </form>
      ) : null}
    </Panel>
  );
}
