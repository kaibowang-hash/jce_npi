import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
} from "react";

import type {
  CreateToolingManufacturingObservationCommand,
  CreateToolingManufacturingPlanCommand,
  ToolingCommandContext,
  ToolingDataSource,
  ToolingManufacturingMilestoneCategory,
  ToolingManufacturingPlanCollectionViewModel,
  ToolingManufacturingPlanDetailViewModel,
  ToolingManufacturingPlanItemViewModel,
  ToolingMilestoneEvidenceRole,
  ToolingPlanEvidenceRole,
  ToolingRevisionCollectionViewModel,
  ToolingSourcingStrategy,
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
type EditorKind = "plan" | "observation";
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

interface ReleasedDocumentDraft {
  key: string;
  revisionGlobalId: string;
  revisionSnapshotHash: string;
  lifecycleGlobalId: string;
  lifecycleVersion: string;
  releaseEventGlobalId: string;
  releaseEventHash: string;
  releaseSnapshotHash: string;
}

interface PlanEvidenceDraft extends ReleasedDocumentDraft {
  role: ToolingPlanEvidenceRole;
}

interface MilestoneDraft {
  key: string;
  category: ToolingManufacturingMilestoneCategory;
  plannedStart: string;
  plannedFinish: string;
  responsibilityKind: "internal" | "supplier";
}

interface PlanDraft {
  toolingRevisionGlobalId: string;
  sourcingStrategy: ToolingSourcingStrategy;
  responsibleMemberGlobalId: string;
  responsibleUserId: string;
  responsibleMemberVersion: string;
  estimateAmount: string;
  budgetAmount: string;
  currency: string;
  reason: string;
  designDocuments: ReleasedDocumentDraft[];
  evidence: PlanEvidenceDraft[];
  milestones: MilestoneDraft[];
}

interface ObservationDraft {
  progressPercentage: string;
  actualStart: string;
  actualFinish: string;
  risk: string;
  note: string;
  evidenceRole: ToolingMilestoneEvidenceRole;
  fileRevisionGlobalId: string;
  fileOptimisticVersion: string;
  frappeContentHash: string;
  sha256: string;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function releasedDocumentDraft(): ReleasedDocumentDraft {
  return {
    key: globalThis.crypto.randomUUID(),
    lifecycleGlobalId: "",
    lifecycleVersion: "1",
    releaseEventGlobalId: "",
    releaseEventHash: "",
    releaseSnapshotHash: "",
    revisionGlobalId: "",
    revisionSnapshotHash: "",
  };
}

function planEvidenceDraft(): PlanEvidenceDraft {
  return { ...releasedDocumentDraft(), role: "dfm" };
}

function milestoneDraft(): MilestoneDraft {
  return {
    category: "design",
    key: globalThis.crypto.randomUUID(),
    plannedFinish: today(),
    plannedStart: today(),
    responsibilityKind: "internal",
  };
}

function planDraft(
  revisions: ToolingRevisionCollectionViewModel | null,
  predecessor: ToolingManufacturingPlanItemViewModel | null,
): PlanDraft {
  const revision =
    revisions?.items.find(
      (item) => item.globalId === predecessor?.plan.toolingRevisionGlobalId,
    ) ?? revisions?.items.at(-1);
  return {
    budgetAmount: predecessor?.plan.budget?.amount ?? "",
    currency:
      predecessor?.plan.engineeringEstimate?.currency ??
      predecessor?.plan.budget?.currency ??
      "CNY",
    designDocuments: predecessor?.plan.designReleaseEvidence.map((item) => ({
      key: globalThis.crypto.randomUUID(),
      ...item,
      lifecycleVersion: String(item.lifecycleVersion),
    })) ?? [releasedDocumentDraft()],
    estimateAmount: predecessor?.plan.engineeringEstimate?.amount ?? "",
    evidence:
      predecessor?.plan.evidence.map((item) => ({
        key: globalThis.crypto.randomUUID(),
        role: item.role,
        ...item.document,
        lifecycleVersion: String(item.document.lifecycleVersion),
      })) ?? [],
    milestones: predecessor?.plan.milestones.map((item) => ({
      category: item.category,
      key: globalThis.crypto.randomUUID(),
      plannedFinish: item.plannedFinish,
      plannedStart: item.plannedStart,
      responsibilityKind: item.responsibilityKind,
    })) ?? [milestoneDraft()],
    reason: "",
    responsibleMemberGlobalId:
      predecessor?.plan.responsibleMember.globalId ?? "",
    responsibleMemberVersion: String(
      predecessor?.plan.responsibleMember.optimisticVersion ?? 1,
    ),
    responsibleUserId: predecessor?.plan.responsibleMember.userId ?? "",
    sourcingStrategy: predecessor?.plan.sourcingStrategy ?? "internal",
    toolingRevisionGlobalId: revision?.globalId ?? "",
  };
}

function observationDraft(): ObservationDraft {
  return {
    actualFinish: "",
    actualStart: "",
    evidenceRole: "progress_evidence",
    fileOptimisticVersion: "1",
    fileRevisionGlobalId: "",
    frappeContentHash: "",
    note: "",
    progressPercentage: "0",
    risk: "",
    sha256: "",
  };
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

function sourcingLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ToolingSourcingStrategy,
): string {
  switch (value) {
    case "internal":
      return t("Internal manufacturing");
    case "supplier":
      return t("Supplier manufacturing");
    case "hybrid":
      return t("Hybrid manufacturing");
  }
}

function categoryLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ToolingManufacturingMilestoneCategory,
): string {
  switch (value) {
    case "design":
      return t("Design");
    case "material_preparation":
      return t("Material preparation");
    case "heat_treatment":
      return t("Heat treatment");
    case "machining":
      return t("Machining");
    case "assembly":
      return t("Assembly");
    case "trial_preparation":
      return t("Trial preparation");
    case "delivery":
      return t("Delivery");
  }
}

function planEvidenceLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ToolingPlanEvidenceRole,
): string {
  switch (value) {
    case "dfm":
      return t("DFM evidence");
    case "tooling_proposal":
      return t("Tooling proposal");
    case "quotation":
      return t("Quotation");
    case "budget":
      return t("Budget evidence");
  }
}

function fileEvidenceLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: ToolingMilestoneEvidenceRole,
): string {
  switch (value) {
    case "progress_evidence":
      return t("Progress evidence");
    case "technical_evidence":
      return t("Technical evidence");
    case "delivery_evidence":
      return t("Delivery evidence");
  }
}

function releaseCapabilityLabel(
  t: ReturnType<typeof useI18n>["t"],
  item: ToolingManufacturingPlanItemViewModel | null,
): string {
  if (!item) return t("No manufacturing plan is selected.");
  if (item.designReleaseEvidence.state === "satisfied")
    return t("Every exact Design Document Revision is released.");
  return item.designReleaseEvidence.reasonCode === "no_design_documents"
    ? t("No Design Document Revision is linked to the Tooling Revision.")
    : t("Exact Design Document release evidence is incomplete.");
}

function latestObservation(
  item: ToolingManufacturingPlanItemViewModel,
  milestoneId: string,
) {
  return item.observations
    .filter((value) => value.milestoneGlobalId === milestoneId)
    .sort(
      (left, right) => right.observationVersion - left.observationVersion,
    )[0];
}

function releasedDocumentValue(value: ReleasedDocumentDraft) {
  return {
    lifecycleGlobalId: value.lifecycleGlobalId.trim(),
    lifecycleVersion: Number(value.lifecycleVersion),
    releaseEventGlobalId: value.releaseEventGlobalId.trim(),
    releaseEventHash: value.releaseEventHash.trim(),
    releaseSnapshotHash: value.releaseSnapshotHash.trim(),
    revisionGlobalId: value.revisionGlobalId.trim(),
    revisionSnapshotHash: value.revisionSnapshotHash.trim(),
  };
}

export default function ToolingManufacturingWorkspace({
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
  const [resource, setResource] = useState<
    ResourceState<{
      plans: ToolingManufacturingPlanCollectionViewModel;
      revisions: ToolingRevisionCollectionViewModel;
    }>
  >({ kind: "loading" });
  const [detail, setDetail] = useState<
    ResourceState<ToolingManufacturingPlanDetailViewModel> | { kind: "idle" }
  >({ kind: "idle" });
  const [selectedPlanRevisionId, setSelectedPlanRevisionId] = useState<
    string | null
  >(null);
  const [selectedMilestoneId, setSelectedMilestoneId] = useState<string | null>(
    null,
  );
  const [editor, setEditor] = useState<EditorKind | null>(null);
  const [planForm, setPlanForm] = useState<PlanDraft>(() =>
    planDraft(null, null),
  );
  const [observationForm, setObservationForm] = useState<ObservationDraft>(() =>
    observationDraft(),
  );
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const retryCommand = useRef<(() => void) | null>(null);
  const editorTrigger = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      dataSource.loadManufacturingPlans(projectId, masterId, controller.signal),
      dataSource.loadToolingRevisions(projectId, masterId, controller.signal),
    ])
      .then(([plans, revisions]) => {
        if (controller.signal.aborted) return;
        setResource({ kind: "loaded", value: { plans, revisions } });
        const selected = plans.items.at(-1)?.plan.globalId ?? null;
        setSelectedPlanRevisionId(selected);
        setDetail(selected ? { kind: "loading" } : { kind: "idle" });
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
    if (!selectedPlanRevisionId) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadManufacturingPlan(
        projectId,
        masterId,
        selectedPlanRevisionId,
        controller.signal,
      )
      .then((value) => {
        if (controller.signal.aborted) return;
        setDetail({ kind: "loaded", value });
        setSelectedMilestoneId(value.item.plan.milestones[0]?.globalId ?? null);
      })
      .catch((error: unknown) => {
        if (
          !controller.signal.aborted &&
          !(error instanceof ToolingRequestCancelledError)
        )
          setDetail({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, masterId, projectId, selectedPlanRevisionId]);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!editor) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity:
        editor === "plan"
          ? `${masterId}:manufacturing-plan`
          : `${selectedPlanRevisionId ?? masterId}:milestone-observation`,
      returnFocusTarget: () => editorTrigger.current,
      version: "unsaved-tooling-manufacturing-context",
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [editor, masterId, reportWorkspaceDirty, selectedPlanRevisionId]);

  const loaded = resource.kind === "loaded" ? resource.value : null;
  const selectedItem = useMemo(() => {
    if (detail.kind === "loaded") return detail.value.item;
    return (
      loaded?.plans.items.find(
        (item) => item.plan.globalId === selectedPlanRevisionId,
      ) ?? null
    );
  }, [detail, loaded?.plans.items, selectedPlanRevisionId]);
  const selectedMilestone = selectedItem?.plan.milestones.find(
    (item) => item.globalId === selectedMilestoneId,
  );

  const runCommand = useCallback(
    <T,>(
      label: string,
      prefix: string,
      operation: (context: ToolingCommandContext) => Promise<T>,
      accept: (value: T) => string | null,
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
            const selected = accept(value);
            setEditor(null);
            setFormError(null);
            setCommand({ kind: "idle" });
            setResource({ kind: "loading" });
            setSelectedPlanRevisionId(selected);
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

  const submitPlan = (): void => {
    if (!loaded || !sessionCommandContext) return;
    const revision = loaded.revisions.items.find(
      (item) => item.globalId === planForm.toolingRevisionGlobalId,
    );
    const memberVersion = Number(planForm.responsibleMemberVersion);
    const completeRelease = (item: ReleasedDocumentDraft) =>
      item.revisionGlobalId.trim() &&
      item.revisionSnapshotHash.trim() &&
      item.lifecycleGlobalId.trim() &&
      Number(item.lifecycleVersion) >= 1 &&
      item.releaseEventGlobalId.trim() &&
      item.releaseEventHash.trim() &&
      item.releaseSnapshotHash.trim();
    if (
      !revision ||
      !planForm.responsibleMemberGlobalId.trim() ||
      !planForm.responsibleUserId.trim() ||
      !Number.isInteger(memberVersion) ||
      memberVersion < 1 ||
      !planForm.reason.trim() ||
      planForm.designDocuments.length < 1 ||
      !planForm.designDocuments.every(completeRelease) ||
      !planForm.evidence.every(completeRelease) ||
      planForm.milestones.length < 1 ||
      planForm.milestones.some(
        (item) =>
          !item.plannedStart ||
          !item.plannedFinish ||
          item.plannedFinish < item.plannedStart,
      )
    ) {
      setFormError(
        t(
          "Complete the exact Revision, member, release evidence and milestone schedule.",
        ),
      );
      return;
    }
    if (
      (planForm.estimateAmount &&
        !/^\d+(?:\.\d+)?$/u.test(planForm.estimateAmount)) ||
      (planForm.budgetAmount &&
        !/^\d+(?:\.\d+)?$/u.test(planForm.budgetAmount)) ||
      ((planForm.estimateAmount || planForm.budgetAmount) &&
        !/^[A-Z]{3}$/u.test(planForm.currency))
    ) {
      setFormError(t("Enter planning amounts with one three-letter currency."));
      return;
    }
    const responsibleMember = {
      globalId: planForm.responsibleMemberGlobalId.trim(),
      optimisticVersion: memberVersion,
      userId: planForm.responsibleUserId.trim(),
    };
    const latest = selectedItem?.plan ?? null;
    const milestoneIds = planForm.milestones.map(() =>
      globalThis.crypto.randomUUID(),
    );
    const payload: CreateToolingManufacturingPlanCommand = {
      ...(latest
        ? {
            expectedVersion: latest.planVersion,
            planGlobalId: latest.planGlobalId,
          }
        : {}),
      ...(planForm.estimateAmount
        ? {
            engineeringEstimate: {
              amount: planForm.estimateAmount,
              currency: planForm.currency,
            },
          }
        : {}),
      ...(planForm.budgetAmount
        ? {
            budget: {
              amount: planForm.budgetAmount,
              currency: planForm.currency,
            },
          }
        : {}),
      designReleaseEvidence: planForm.designDocuments.map(
        releasedDocumentValue,
      ),
      evidence: planForm.evidence.map((item) => ({
        document: releasedDocumentValue(item),
        role: item.role,
      })),
      milestones: planForm.milestones.map((item, index) => ({
        category: item.category,
        globalId: milestoneIds[index] ?? globalThis.crypto.randomUUID(),
        plannedFinish: item.plannedFinish,
        plannedStart: item.plannedStart,
        predecessorGlobalIds: index ? [milestoneIds[index - 1] ?? ""] : [],
        responsibleMember:
          item.responsibilityKind === "internal" ? responsibleMember : null,
        responsibilityKind: item.responsibilityKind,
        sequence: index + 1,
      })),
      reason: planForm.reason.trim(),
      responsibleMember,
      sourcingStrategy: planForm.sourcingStrategy,
      toolingRevisionGlobalId: revision.globalId,
      toolingRevisionSnapshotHash: revision.snapshotHash,
    };
    runCommand(
      latest
        ? t("Appending manufacturing plan Revision")
        : t("Creating manufacturing plan"),
      "tooling-manufacturing-plan",
      (context) =>
        dataSource.createManufacturingPlan(
          projectId,
          masterId,
          payload,
          context,
        ),
      (value) => value.plan.globalId,
    );
  };

  const submitObservation = (): void => {
    if (!selectedItem || !selectedMilestone || !sessionCommandContext) return;
    const progress = Number(observationForm.progressPercentage);
    const evidenceValues = [
      observationForm.fileRevisionGlobalId,
      observationForm.frappeContentHash,
      observationForm.sha256,
    ];
    const evidenceStarted = evidenceValues.some((value) => value.trim());
    const evidenceVersion = Number(observationForm.fileOptimisticVersion);
    if (
      !Number.isInteger(progress) ||
      progress < 0 ||
      progress > 100 ||
      (observationForm.actualFinish && !observationForm.actualStart) ||
      (observationForm.actualStart &&
        observationForm.actualFinish &&
        observationForm.actualFinish < observationForm.actualStart) ||
      (evidenceStarted &&
        (evidenceValues.some((value) => !value.trim()) ||
          !Number.isInteger(evidenceVersion) ||
          evidenceVersion < 1))
    ) {
      setFormError(
        t(
          "Enter valid progress, actual dates and complete optional File evidence.",
        ),
      );
      return;
    }
    const predecessor = latestObservation(
      selectedItem,
      selectedMilestone.globalId,
    );
    const payload: CreateToolingManufacturingObservationCommand = {
      ...(predecessor
        ? { expectedVersion: predecessor.observationVersion }
        : {}),
      ...(observationForm.actualStart
        ? { actualStart: observationForm.actualStart }
        : {}),
      ...(observationForm.actualFinish
        ? { actualFinish: observationForm.actualFinish }
        : {}),
      ...(observationForm.risk.trim()
        ? { risk: observationForm.risk.trim() }
        : {}),
      ...(observationForm.note.trim()
        ? { note: observationForm.note.trim() }
        : {}),
      evidence: evidenceStarted
        ? [
            {
              fileOptimisticVersion: evidenceVersion,
              fileRevisionGlobalId: observationForm.fileRevisionGlobalId.trim(),
              frappeContentHash: observationForm.frappeContentHash.trim(),
              role: observationForm.evidenceRole,
              sha256: observationForm.sha256.trim(),
            },
          ]
        : [],
      milestoneSnapshotHash: selectedMilestone.snapshotHash,
      planRevisionSnapshotHash: selectedItem.plan.snapshotHash,
      progressPercentage: progress,
    };
    runCommand(
      t("Recording internal milestone observation"),
      "tooling-manufacturing-observation",
      (context) =>
        dataSource.createManufacturingObservation(
          projectId,
          masterId,
          selectedItem.plan.globalId,
          selectedMilestone.globalId,
          payload,
          context,
        ),
      (value) => value.observation.planRevisionGlobalId,
    );
  };

  if (resource.kind === "failed") {
    return (
      <Panel
        id="tooling-manufacturing-workspace"
        title={t("Manufacturing and supplier workspace")}
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
        id="tooling-manufacturing-workspace"
        title={t("Manufacturing and supplier workspace")}
      >
        <p aria-busy="true" role="status">
          {t("Loading manufacturing plan workspace")}
        </p>
      </Panel>
    );
  }

  const processing = command.kind === "processing";
  const canCreate =
    loaded.plans.permissions.createPlan && sessionCommandContext !== null;
  const canObserve =
    loaded.plans.permissions.observeMilestone &&
    sessionCommandContext !== null &&
    selectedMilestone !== undefined;
  const currentObservation =
    selectedItem && selectedMilestone
      ? latestObservation(selectedItem, selectedMilestone.globalId)
      : undefined;

  return (
    <Panel
      id="tooling-manufacturing-workspace"
      title={t("Manufacturing and supplier workspace")}
    >
      <div className="tooling-set__toolbar">
        <div>
          <SemanticStatus
            label={loaded.plans.items.length ? t("Available") : t("Empty")}
            tone={loaded.plans.items.length ? "success" : "neutral"}
          />
          <span>
            {t("Immutable plan Revisions")}:{" "}
            {formatNumber(locale, loaded.plans.items.length, 0)}
          </span>
        </div>
        {loaded.plans.permissions.createPlan && !editor ? (
          <Button
            disabled={
              !canCreate || processing || loaded.revisions.items.length === 0
            }
            onClick={(event) => {
              editorTrigger.current = event.currentTarget;
              setPlanForm(planDraft(loaded.revisions, selectedItem));
              setFormError(null);
              setEditor("plan");
            }}
            visual="primary"
          >
            {selectedItem
              ? t("Append plan Revision")
              : t("Create manufacturing plan")}
          </Button>
        ) : null}
      </div>

      {!sessionCommandContext &&
      (loaded.plans.permissions.createPlan ||
        loaded.plans.permissions.observeMilestone) ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Manufacturing data is read only in this session.")}</span>
          <span>
            {t(
              "Session verification is required before a command can be submitted.",
            )}
          </span>
        </div>
      ) : null}
      {!loaded.plans.permissions.createPlan &&
      !loaded.plans.permissions.observeMilestone ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>
            {t("Manufacturing history is read only for this account.")}
          </span>
          <span>
            {t("The server controls plan and observation capabilities.")}
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

      <div className="tooling-manufacturing__capabilities">
        <section aria-label={t("Design release evidence")}>
          <strong>{t("Design release evidence")}</strong>
          <SemanticStatus
            label={
              selectedItem?.designReleaseEvidence.state === "satisfied"
                ? t("Satisfied")
                : t("Blocked")
            }
            tone={
              selectedItem?.designReleaseEvidence.state === "satisfied"
                ? "success"
                : "warning"
            }
          />
          <span>{releaseCapabilityLabel(t, selectedItem)}</span>
        </section>
        <section aria-label={t("Manufacturing authorization")}>
          <strong>{t("Manufacturing authorization")}</strong>
          <SemanticStatus label={t("Unavailable")} tone="warning" />
          <span>{t("Tooling lifecycle policy is not approved.")}</span>
        </section>
        <section aria-label={t("ERPNext procurement and actual cost")}>
          <strong>{t("ERPNext procurement and actual cost")}</strong>
          <SemanticStatus
            label={
              loaded.plans.erpProjection.state === "available"
                ? t("Read only")
                : t("Unavailable")
            }
            tone={
              loaded.plans.erpProjection.state === "available"
                ? "info"
                : "warning"
            }
          />
          <span>
            {loaded.plans.erpProjection.state === "available"
              ? t("Formal Supplier and actual cost are observed from ERPNext.")
              : t(
                  "ERPNext procurement and actual-cost projection is unavailable.",
                )}
          </span>
        </section>
      </div>

      {loaded.plans.items.length === 0 ? (
        <div className="empty-state" role="status">
          <strong>{t("No manufacturing plan has been recorded.")}</strong>
          <span>
            {t(
              "Create an internal immutable plan without inferring funding, PO or manufacturing approval.",
            )}
          </span>
        </div>
      ) : (
        <div className="tooling-manufacturing__layout">
          <section aria-label={t("Manufacturing plan history")}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("Plan Revision")}</th>
                  <th>{t("Sourcing")}</th>
                  <th>{t("Tooling Revision")}</th>
                  <th>{t("Milestones")}</th>
                  <th>{t("Observations")}</th>
                </tr>
              </thead>
              <tbody>
                {loaded.plans.items.map((item) => (
                  <tr
                    aria-selected={
                      item.plan.globalId === selectedPlanRevisionId
                    }
                    key={item.plan.globalId}
                  >
                    <td>
                      <button
                        className="table-link"
                        onClick={() => {
                          setDetail({ kind: "loading" });
                          setSelectedPlanRevisionId(item.plan.globalId);
                        }}
                        type="button"
                      >
                        {formatNumber(locale, item.plan.planVersion, 0)} ·{" "}
                        <span data-language-exempt="identifier">
                          {item.plan.globalId.slice(0, 8)}
                        </span>
                      </button>
                    </td>
                    <td>{sourcingLabel(t, item.plan.sourcingStrategy)}</td>
                    <td data-language-exempt="identifier">
                      {item.plan.toolingRevisionGlobalId.slice(0, 8)}
                    </td>
                    <td>
                      {formatNumber(locale, item.plan.milestones.length, 0)}
                    </td>
                    <td>{formatNumber(locale, item.observations.length, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <aside
            aria-label={t("Manufacturing plan inspector")}
            className="tooling-set__inspector"
          >
            {detail.kind === "loading" ? (
              <p aria-busy="true" role="status">
                {t("Loading exact plan Revision")}
              </p>
            ) : detail.kind === "failed" ? (
              <RequestFailurePanel failure={detail.failure} />
            ) : selectedItem ? (
              <>
                <DefinitionList
                  rows={[
                    {
                      exempt: "identifier",
                      label: t("Plan identity"),
                      value: selectedItem.plan.planGlobalId,
                    },
                    {
                      label: t("Plan version"),
                      value: formatNumber(
                        locale,
                        selectedItem.plan.planVersion,
                        0,
                      ),
                    },
                    {
                      exempt: "business-data",
                      label: t("Responsible member"),
                      value: selectedItem.plan.responsibleMember.userId,
                    },
                    {
                      exempt: "identifier",
                      label: t("Snapshot hash"),
                      value: selectedItem.plan.snapshotHash,
                    },
                  ]}
                />
                <small>
                  {t(
                    "Plan progress never authorizes manufacturing or changes ERPNext truth.",
                  )}
                </small>
              </>
            ) : null}
          </aside>
        </div>
      )}

      {selectedItem ? (
        <section className="tooling-manufacturing__milestones">
          <div className="tooling-set__toolbar">
            <div>
              <strong>{t("Manufacturing milestones")}</strong>
              <span>
                {t("Internal NPI observations")}:{" "}
                {formatNumber(locale, selectedItem.observations.length, 0)}
              </span>
            </div>
            {loaded.plans.permissions.observeMilestone && !editor ? (
              <Button
                disabled={!canObserve || processing}
                onClick={(event) => {
                  editorTrigger.current = event.currentTarget;
                  setObservationForm(observationDraft());
                  setFormError(null);
                  setEditor("observation");
                }}
              >
                {t("Record observation")}
              </Button>
            ) : null}
          </div>
          <div className="table-scroll" tabIndex={0}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("Sequence")}</th>
                  <th>{t("Category")}</th>
                  <th>{t("Planned dates")}</th>
                  <th>{t("Responsibility")}</th>
                  <th>{t("Latest progress")}</th>
                  <th>{t("Evidence")}</th>
                </tr>
              </thead>
              <tbody>
                {selectedItem.plan.milestones.map((item) => {
                  const observation = latestObservation(
                    selectedItem,
                    item.globalId,
                  );
                  return (
                    <tr
                      aria-selected={item.globalId === selectedMilestoneId}
                      key={item.globalId}
                    >
                      <td>
                        <button
                          className="table-link"
                          onClick={() => {
                            setSelectedMilestoneId(item.globalId);
                          }}
                          type="button"
                        >
                          {formatNumber(locale, item.sequence, 0)}
                        </button>
                      </td>
                      <td>{categoryLabel(t, item.category)}</td>
                      <td>
                        <time dateTime={item.plannedStart}>
                          {formatDate(locale, item.plannedStart)}
                        </time>{" "}
                        –{" "}
                        <time dateTime={item.plannedFinish}>
                          {formatDate(locale, item.plannedFinish)}
                        </time>
                      </td>
                      <td>
                        {item.responsibilityKind === "supplier"
                          ? t("Supplier-responsible, internally reported")
                          : t("Internal Project member")}
                      </td>
                      <td>
                        {observation
                          ? `${formatNumber(locale, observation.progressPercentage, 0)}%`
                          : t("No observation")}
                      </td>
                      <td>
                        {observation
                          ? formatNumber(locale, observation.evidence.length, 0)
                          : formatNumber(locale, 0, 0)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {currentObservation ? (
            <div className="tooling-manufacturing__observation" role="status">
              <SemanticStatus
                label={t("Latest internal observation")}
                tone="info"
              />
              <span>
                {formatNumber(locale, currentObservation.progressPercentage, 0)}
                %
              </span>
              <span data-language-exempt="business-data">
                {currentObservation.risk ?? t("No risk recorded")}
              </span>
              <span data-language-exempt="business-data">
                {currentObservation.note ?? t("No note recorded")}
              </span>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="tooling-manufacturing__erp">
        <strong>{t("Formal Supplier and ERPNext actual cost")}</strong>
        {loaded.plans.erpProjection.state === "unavailable" ? (
          <div
            className="scenario-banner scenario-banner--read-only"
            role="status"
          >
            <span>{t("ERPNext source truth is unavailable.")}</span>
            <span>
              {t(
                "No Supplier, PO, receipt, invoice or actual cost is inferred as zero.",
              )}
            </span>
          </div>
        ) : (
          <>
            <DefinitionList
              rows={[
                {
                  exempt: "business-data",
                  label: t("Formal Supplier"),
                  value: loaded.plans.erpProjection.supplier.supplierName,
                },
                {
                  exempt: "identifier",
                  label: t("Target version"),
                  value: loaded.plans.erpProjection.targetVersion,
                },
                {
                  label: t("Actual-cost rows"),
                  value: formatNumber(
                    locale,
                    loaded.plans.erpProjection.rows.length,
                    0,
                  ),
                },
              ]}
            />
            <div className="table-scroll" tabIndex={0}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("Cost type code")}</th>
                    <th>{t("Currency")}</th>
                    <th>{t("Actual cost")}</th>
                  </tr>
                </thead>
                <tbody>
                  {loaded.plans.erpProjection.summaries.map((item) => (
                    <tr
                      key={`${item.supplierSourceObjectId}-${item.costTypeCode}-${item.currency}`}
                    >
                      <td data-language-exempt="business-data">
                        {item.costTypeCode}
                      </td>
                      <td data-language-exempt="unit">{item.currency}</td>
                      <td data-language-exempt="business-data">
                        {item.amount}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {editor === "plan" ? (
        <form
          className="tooling-manufacturing__form"
          onSubmit={(event) => {
            event.preventDefault();
            submitPlan();
          }}
        >
          <h3>
            {selectedItem
              ? t("Append immutable manufacturing plan Revision")
              : t("Create immutable manufacturing plan")}
          </h3>
          <div className="form-grid form-grid--two">
            <label>
              <span>{t("Exact Tooling Revision")}</span>
              <Select
                disabled={processing}
                onChange={(event) => {
                  setPlanForm({
                    ...planForm,
                    toolingRevisionGlobalId: event.currentTarget.value,
                  });
                }}
                value={planForm.toolingRevisionGlobalId}
              >
                {loaded.revisions.items.map((item) => (
                  <option key={item.globalId} value={item.globalId}>
                    {item.revisionLabel} · {item.revisionNumber}
                  </option>
                ))}
              </Select>
            </label>
            <label>
              <span>{t("Sourcing strategy")}</span>
              <Select
                disabled={processing}
                onChange={(event) => {
                  setPlanForm({
                    ...planForm,
                    sourcingStrategy: event.currentTarget
                      .value as ToolingSourcingStrategy,
                  });
                }}
                value={planForm.sourcingStrategy}
              >
                {(["internal", "supplier", "hybrid"] as const).map((item) => (
                  <option key={item} value={item}>
                    {sourcingLabel(t, item)}
                  </option>
                ))}
              </Select>
            </label>
            <LabeledInput
              disabled={processing}
              label={t("Responsible member identity")}
              onChange={(event) => {
                setPlanForm({
                  ...planForm,
                  responsibleMemberGlobalId: event.currentTarget.value,
                });
              }}
              value={planForm.responsibleMemberGlobalId}
            />
            <LabeledInput
              disabled={processing}
              label={t("Responsible user")}
              onChange={(event) => {
                setPlanForm({
                  ...planForm,
                  responsibleUserId: event.currentTarget.value,
                });
              }}
              value={planForm.responsibleUserId}
            />
            <LabeledInput
              disabled={processing}
              label={t("Member version")}
              min="1"
              onChange={(event) => {
                setPlanForm({
                  ...planForm,
                  responsibleMemberVersion: event.currentTarget.value,
                });
              }}
              type="number"
              value={planForm.responsibleMemberVersion}
            />
            <LabeledInput
              disabled={processing}
              label={t("Currency")}
              maxLength={3}
              onChange={(event) => {
                setPlanForm({
                  ...planForm,
                  currency: event.currentTarget.value.toUpperCase(),
                });
              }}
              value={planForm.currency}
            />
            <LabeledInput
              disabled={processing}
              label={t("Engineering estimate")}
              onChange={(event) => {
                setPlanForm({
                  ...planForm,
                  estimateAmount: event.currentTarget.value,
                });
              }}
              value={planForm.estimateAmount}
            />
            <LabeledInput
              disabled={processing}
              label={t("Budget fact")}
              onChange={(event) => {
                setPlanForm({
                  ...planForm,
                  budgetAmount: event.currentTarget.value,
                });
              }}
              value={planForm.budgetAmount}
            />
          </div>

          <fieldset className="tooling-manufacturing__field-array">
            <legend>{t("Exact released Design Documents")}</legend>
            {planForm.designDocuments.map((item, index) => (
              <div className="form-grid form-grid--two" key={item.key}>
                <LabeledInput
                  disabled={processing}
                  label={t("Document Revision identity")}
                  onChange={(event) => {
                    const values = [...planForm.designDocuments];
                    values[index] = {
                      ...item,
                      revisionGlobalId: event.currentTarget.value,
                    };
                    setPlanForm({ ...planForm, designDocuments: values });
                  }}
                  value={item.revisionGlobalId}
                />
                <LabeledInput
                  disabled={processing}
                  label={t("Document Revision snapshot hash")}
                  onChange={(event) => {
                    const values = [...planForm.designDocuments];
                    values[index] = {
                      ...item,
                      revisionSnapshotHash: event.currentTarget.value,
                    };
                    setPlanForm({ ...planForm, designDocuments: values });
                  }}
                  value={item.revisionSnapshotHash}
                />
                <LabeledInput
                  disabled={processing}
                  label={t("Document lifecycle identity")}
                  onChange={(event) => {
                    const values = [...planForm.designDocuments];
                    values[index] = {
                      ...item,
                      lifecycleGlobalId: event.currentTarget.value,
                    };
                    setPlanForm({ ...planForm, designDocuments: values });
                  }}
                  value={item.lifecycleGlobalId}
                />
                <LabeledInput
                  disabled={processing}
                  label={t("Document lifecycle version")}
                  min="1"
                  onChange={(event) => {
                    const values = [...planForm.designDocuments];
                    values[index] = {
                      ...item,
                      lifecycleVersion: event.currentTarget.value,
                    };
                    setPlanForm({ ...planForm, designDocuments: values });
                  }}
                  type="number"
                  value={item.lifecycleVersion}
                />
                <LabeledInput
                  disabled={processing}
                  label={t("Release event identity")}
                  onChange={(event) => {
                    const values = [...planForm.designDocuments];
                    values[index] = {
                      ...item,
                      releaseEventGlobalId: event.currentTarget.value,
                    };
                    setPlanForm({ ...planForm, designDocuments: values });
                  }}
                  value={item.releaseEventGlobalId}
                />
                <LabeledInput
                  disabled={processing}
                  label={t("Release event hash")}
                  onChange={(event) => {
                    const values = [...planForm.designDocuments];
                    values[index] = {
                      ...item,
                      releaseEventHash: event.currentTarget.value,
                    };
                    setPlanForm({ ...planForm, designDocuments: values });
                  }}
                  value={item.releaseEventHash}
                />
                <LabeledInput
                  disabled={processing}
                  label={t("Release snapshot hash")}
                  onChange={(event) => {
                    const values = [...planForm.designDocuments];
                    values[index] = {
                      ...item,
                      releaseSnapshotHash: event.currentTarget.value,
                    };
                    setPlanForm({ ...planForm, designDocuments: values });
                  }}
                  value={item.releaseSnapshotHash}
                />
                {planForm.designDocuments.length > 1 ? (
                  <Button
                    disabled={processing}
                    onClick={() => {
                      setPlanForm({
                        ...planForm,
                        designDocuments: planForm.designDocuments.filter(
                          (value) => value.key !== item.key,
                        ),
                      });
                    }}
                    type="button"
                  >
                    {t("Remove released Document")}
                  </Button>
                ) : null}
              </div>
            ))}
            <Button
              disabled={processing || planForm.designDocuments.length >= 50}
              onClick={() => {
                setPlanForm({
                  ...planForm,
                  designDocuments: [
                    ...planForm.designDocuments,
                    releasedDocumentDraft(),
                  ],
                });
              }}
              type="button"
            >
              {t("Add released Document")}
            </Button>
          </fieldset>

          <fieldset className="tooling-manufacturing__field-array">
            <legend>{t("Manufacturing milestone schedule")}</legend>
            {planForm.milestones.map((item, index) => (
              <div
                className="tooling-manufacturing__milestone-editor"
                key={item.key}
              >
                <span>
                  {t("Sequence")} {formatNumber(locale, index + 1, 0)}
                </span>
                <label>
                  <span>{t("Category")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      const values = [...planForm.milestones];
                      values[index] = {
                        ...item,
                        category: event.currentTarget
                          .value as ToolingManufacturingMilestoneCategory,
                      };
                      setPlanForm({ ...planForm, milestones: values });
                    }}
                    value={item.category}
                  >
                    {(
                      [
                        "design",
                        "material_preparation",
                        "heat_treatment",
                        "machining",
                        "assembly",
                        "trial_preparation",
                        "delivery",
                      ] as const
                    ).map((category) => (
                      <option key={category} value={category}>
                        {categoryLabel(t, category)}
                      </option>
                    ))}
                  </Select>
                </label>
                <LabeledInput
                  disabled={processing}
                  label={t("Planned start")}
                  onChange={(event) => {
                    const values = [...planForm.milestones];
                    values[index] = {
                      ...item,
                      plannedStart: event.currentTarget.value,
                    };
                    setPlanForm({ ...planForm, milestones: values });
                  }}
                  type="date"
                  value={item.plannedStart}
                />
                <LabeledInput
                  disabled={processing}
                  label={t("Planned finish")}
                  onChange={(event) => {
                    const values = [...planForm.milestones];
                    values[index] = {
                      ...item,
                      plannedFinish: event.currentTarget.value,
                    };
                    setPlanForm({ ...planForm, milestones: values });
                  }}
                  type="date"
                  value={item.plannedFinish}
                />
                <label>
                  <span>{t("Responsibility")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      const values = [...planForm.milestones];
                      values[index] = {
                        ...item,
                        responsibilityKind: event.currentTarget.value as
                          | "internal"
                          | "supplier",
                      };
                      setPlanForm({ ...planForm, milestones: values });
                    }}
                    value={item.responsibilityKind}
                  >
                    <option value="internal">{t("Internal")}</option>
                    <option value="supplier">
                      {t("Supplier-responsible, internally reported")}
                    </option>
                  </Select>
                </label>
                {planForm.milestones.length > 1 ? (
                  <Button
                    disabled={processing}
                    onClick={() => {
                      setPlanForm({
                        ...planForm,
                        milestones: planForm.milestones.filter(
                          (value) => value.key !== item.key,
                        ),
                      });
                    }}
                    type="button"
                  >
                    {t("Remove milestone")}
                  </Button>
                ) : null}
              </div>
            ))}
            <Button
              disabled={processing || planForm.milestones.length >= 100}
              onClick={() => {
                setPlanForm({
                  ...planForm,
                  milestones: [...planForm.milestones, milestoneDraft()],
                });
              }}
              type="button"
            >
              {t("Add milestone")}
            </Button>
          </fieldset>

          <fieldset className="tooling-manufacturing__field-array">
            <legend>{t("Optional released planning evidence")}</legend>
            {planForm.evidence.map((item, index) => (
              <div className="form-grid form-grid--two" key={item.key}>
                <label>
                  <span>{t("Evidence role")}</span>
                  <Select
                    disabled={processing}
                    onChange={(event) => {
                      const values = [...planForm.evidence];
                      values[index] = {
                        ...item,
                        role: event.currentTarget
                          .value as ToolingPlanEvidenceRole,
                      };
                      setPlanForm({ ...planForm, evidence: values });
                    }}
                    value={item.role}
                  >
                    {(
                      [
                        "dfm",
                        "tooling_proposal",
                        "quotation",
                        "budget",
                      ] as const
                    ).map((role) => (
                      <option key={role} value={role}>
                        {planEvidenceLabel(t, role)}
                      </option>
                    ))}
                  </Select>
                </label>
                {(
                  [
                    ["revisionGlobalId", t("Document Revision identity")],
                    [
                      "revisionSnapshotHash",
                      t("Document Revision snapshot hash"),
                    ],
                    ["lifecycleGlobalId", t("Document lifecycle identity")],
                    ["lifecycleVersion", t("Document lifecycle version")],
                    ["releaseEventGlobalId", t("Release event identity")],
                    ["releaseEventHash", t("Release event hash")],
                    ["releaseSnapshotHash", t("Release snapshot hash")],
                  ] as const
                ).map(([field, label]) => (
                  <LabeledInput
                    disabled={processing}
                    key={field}
                    label={label}
                    onChange={(event) => {
                      const values = [...planForm.evidence];
                      values[index] = {
                        ...item,
                        [field]: event.currentTarget.value,
                      };
                      setPlanForm({ ...planForm, evidence: values });
                    }}
                    type={field === "lifecycleVersion" ? "number" : "text"}
                    value={item[field]}
                  />
                ))}
                <Button
                  disabled={processing}
                  onClick={() => {
                    setPlanForm({
                      ...planForm,
                      evidence: planForm.evidence.filter(
                        (value) => value.key !== item.key,
                      ),
                    });
                  }}
                  type="button"
                >
                  {t("Remove planning evidence")}
                </Button>
              </div>
            ))}
            <Button
              disabled={processing || planForm.evidence.length >= 4}
              onClick={() => {
                setPlanForm({
                  ...planForm,
                  evidence: [...planForm.evidence, planEvidenceDraft()],
                });
              }}
              type="button"
            >
              {t("Add planning evidence")}
            </Button>
          </fieldset>

          <label>
            <span>{t("Revision reason")}</span>
            <textarea
              className="npi-input"
              disabled={processing}
              maxLength={500}
              onChange={(event) => {
                setPlanForm({ ...planForm, reason: event.currentTarget.value });
              }}
              value={planForm.reason}
            />
          </label>
          {formError ? <p role="alert">{formError}</p> : null}
          <div className="detail-actions">
            <Button disabled={processing} type="submit" visual="primary">
              {selectedItem
                ? t("Append immutable plan Revision")
                : t("Create immutable plan")}
            </Button>
            <Button
              disabled={processing}
              onClick={() => {
                setEditor(null);
                setFormError(null);
                globalThis.queueMicrotask(() => editorTrigger.current?.focus());
              }}
              type="button"
            >
              {t("Cancel")}
            </Button>
          </div>
        </form>
      ) : null}

      {editor === "observation" && selectedMilestone ? (
        <form
          className="tooling-manufacturing__form"
          onSubmit={(event) => {
            event.preventDefault();
            submitObservation();
          }}
        >
          <h3>{t("Record internal milestone observation")}</h3>
          <p>
            {selectedMilestone.responsibilityKind === "supplier"
              ? t(
                  "This supplier-responsible milestone is still reported by an internal NPI user.",
                )
              : t(
                  "The authenticated internal NPI user reports this observation.",
                )}
          </p>
          <div className="form-grid form-grid--two">
            <LabeledInput
              disabled={processing}
              label={t("Progress percentage")}
              max="100"
              min="0"
              onChange={(event) => {
                setObservationForm({
                  ...observationForm,
                  progressPercentage: event.currentTarget.value,
                });
              }}
              type="number"
              value={observationForm.progressPercentage}
            />
            <LabeledInput
              disabled={processing}
              label={t("Actual start")}
              onChange={(event) => {
                setObservationForm({
                  ...observationForm,
                  actualStart: event.currentTarget.value,
                });
              }}
              type="date"
              value={observationForm.actualStart}
            />
            <LabeledInput
              disabled={processing}
              label={t("Actual finish")}
              onChange={(event) => {
                setObservationForm({
                  ...observationForm,
                  actualFinish: event.currentTarget.value,
                });
              }}
              type="date"
              value={observationForm.actualFinish}
            />
            <LabeledInput
              disabled={processing}
              label={t("Risk")}
              maxLength={240}
              onChange={(event) => {
                setObservationForm({
                  ...observationForm,
                  risk: event.currentTarget.value,
                });
              }}
              value={observationForm.risk}
            />
          </div>
          <label>
            <span>{t("Observation note")}</span>
            <textarea
              className="npi-input"
              disabled={processing}
              maxLength={1000}
              onChange={(event) => {
                setObservationForm({
                  ...observationForm,
                  note: event.currentTarget.value,
                });
              }}
              value={observationForm.note}
            />
          </label>
          <fieldset className="tooling-manufacturing__field-array">
            <legend>{t("Optional clean private File evidence")}</legend>
            <div className="form-grid form-grid--two">
              <label>
                <span>{t("Evidence role")}</span>
                <Select
                  disabled={processing}
                  onChange={(event) => {
                    setObservationForm({
                      ...observationForm,
                      evidenceRole: event.currentTarget
                        .value as ToolingMilestoneEvidenceRole,
                    });
                  }}
                  value={observationForm.evidenceRole}
                >
                  {(
                    [
                      "progress_evidence",
                      "technical_evidence",
                      "delivery_evidence",
                    ] as const
                  ).map((role) => (
                    <option key={role} value={role}>
                      {fileEvidenceLabel(t, role)}
                    </option>
                  ))}
                </Select>
              </label>
              <LabeledInput
                disabled={processing}
                label={t("File Revision identity")}
                onChange={(event) => {
                  setObservationForm({
                    ...observationForm,
                    fileRevisionGlobalId: event.currentTarget.value,
                  });
                }}
                value={observationForm.fileRevisionGlobalId}
              />
              <LabeledInput
                disabled={processing}
                label={t("File version")}
                min="1"
                onChange={(event) => {
                  setObservationForm({
                    ...observationForm,
                    fileOptimisticVersion: event.currentTarget.value,
                  });
                }}
                type="number"
                value={observationForm.fileOptimisticVersion}
              />
              <LabeledInput
                disabled={processing}
                label={t("Frappe content hash")}
                onChange={(event) => {
                  setObservationForm({
                    ...observationForm,
                    frappeContentHash: event.currentTarget.value,
                  });
                }}
                value={observationForm.frappeContentHash}
              />
              <LabeledInput
                disabled={processing}
                label={t("SHA-256")}
                onChange={(event) => {
                  setObservationForm({
                    ...observationForm,
                    sha256: event.currentTarget.value,
                  });
                }}
                value={observationForm.sha256}
              />
            </div>
          </fieldset>
          {formError ? <p role="alert">{formError}</p> : null}
          <div className="detail-actions">
            <Button disabled={processing} type="submit" visual="primary">
              {t("Record immutable observation")}
            </Button>
            <Button
              disabled={processing}
              onClick={() => {
                setEditor(null);
                setFormError(null);
                globalThis.queueMicrotask(() => editorTrigger.current?.focus());
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
