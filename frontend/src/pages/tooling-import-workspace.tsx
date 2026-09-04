import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  type ToolingImportBatchCollection,
  type ToolingImportBatchDetail,
  type ToolingImportCorrectionArtifact,
  type ToolingImportDataSource,
  type ToolingImportJobSnapshot,
  type ToolingImportJobState,
  type ToolingImportReconciliationRevision,
} from "../api/tooling-import-data-source";
import { ToolingRequestCancelledError } from "../api/tooling-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import {
  DockedInspector,
  MetricStrip,
  ObjectHeader,
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

type ImportStep =
  | "upload"
  | "detect"
  | "map"
  | "transform"
  | "validate"
  | "preview"
  | "execute"
  | "audit";

type ResourceState<T> =
  | { kind: "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };

type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

interface SourceDraft {
  customerScopeId: string;
  fileRevisionGlobalId: string;
  fileOptimisticVersion: string;
  frappeContentHash: string;
  sha256: string;
}

interface MappingDraft {
  templateKey: string;
  reason: string;
}

interface ConfirmationDraft {
  kind: "image_anchor" | "relationship";
  worksheetName: string;
  sourceRow: string;
  anchorKey: string;
  selectedTargetObject: "part_revision" | "tooling_master";
  selectedTargetGlobalId: string;
  selectedTargetSnapshotHash: string;
  reason: string;
}

interface CorrectionDraft {
  worksheetName: string;
  sourceRow: string;
  sourceHeader: string;
  correctedValue: string;
}

const source = {
  editableIn: "NPI_ONE" as const,
  sourceSystem: "NPI_ONE" as const,
  syncState: "local" as const,
};

const steps: readonly ImportStep[] = [
  "upload",
  "detect",
  "map",
  "transform",
  "validate",
  "preview",
  "execute",
  "audit",
];

function stepLabel(
  t: ReturnType<typeof useI18n>["t"],
  step: ImportStep,
): string {
  switch (step) {
    case "upload":
      return t("Upload");
    case "detect":
      return t("Detect");
    case "map":
      return t("Map");
    case "transform":
      return t("Transform");
    case "validate":
      return t("Validate");
    case "preview":
      return t("Preview");
    case "execute":
      return t("Execute");
    case "audit":
      return t("Audit");
  }
}

function jobStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: ToolingImportJobState,
): string {
  switch (state) {
    case "queued":
      return t("Queued");
    case "processing":
      return t("Processing");
    case "partially_succeeded":
      return t("Partially succeeded");
    case "succeeded":
      return t("Succeeded");
    case "failed_retryable":
      return t("Retryable failure");
    case "failed_final":
      return t("Final failure");
    case "rolled_back":
      return t("Rolled back");
    case "rollback_denied":
      return t("Rollback denied");
  }
}

function jobTone(
  state: ToolingImportJobState,
): "neutral" | "info" | "success" | "warning" | "danger" {
  if (state === "succeeded" || state === "rolled_back") return "success";
  if (state === "queued" || state === "processing") return "info";
  if (state === "partially_succeeded" || state === "failed_retryable")
    return "warning";
  return "danger";
}

function rowStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: ToolingImportJobSnapshot["rowResults"][number]["state"],
): string {
  switch (state) {
    case "created":
      return t("Created");
    case "updated":
      return t("Updated");
    case "skipped":
      return t("Skipped");
    case "failed_retryable":
      return t("Retryable failure");
    case "failed_final":
      return t("Final failure");
    case "confirmation_required":
      return t("Confirmation required");
  }
}

function resultCodeLabel(
  t: ReturnType<typeof useI18n>["t"],
  code: string,
): string {
  switch (code) {
    case "created":
      return t("The field was imported.");
    case "retained_provenance":
      return t("The source field was retained as import provenance.");
    case "unexpected_retryable_failure":
      return t(
        "The row could not be imported. Retry with the trace identifier.",
      );
    case "formula_error":
      return t("Correct the workbook formula error.");
    case "state_in_identifier":
      return t("Confirm the state separated from the Tooling number.");
    case "tooling_number_missing":
      return t("Enter a Tooling number or confirm a supported relationship.");
    case "mixed_or_invalid_unit":
      return t("Enter one supported value and unit.");
    case "mixed_tonnage_machine_type":
      return t("Confirm clamp tonnage and machine type separately.");
    case "legacy_grade_uninterpreted":
      return t("Legacy Grade is retained without inferred meaning.");
    case "relationship_confirmation_required":
      return t("Confirm the proposed Tooling relationship.");
    case "required_value_missing":
      return t("Enter the required source value.");
    case "unmapped_source_column":
      return t("Confirm how the unmapped source column should be handled.");
    case "execution_not_eligible":
      return t("The preview row is not eligible for execution.");
    default:
      return t("See the trace identifier for the exact failure.");
  }
}

function reconciliationStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: ToolingImportReconciliationRevision["items"][number]["state"],
): string {
  switch (state) {
    case "matched":
      return t("Matched");
    case "missing":
      return t("Missing");
    case "changed":
      return t("Changed");
    case "downstream_used":
      return t("Used downstream");
    case "rolled_back":
      return t("Rolled back");
  }
}

function canRetryFailure(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function last<T>(items: readonly T[]): T | null {
  return items.at(-1) ?? null;
}

function emptySourceDraft(): SourceDraft {
  return {
    customerScopeId: "",
    fileRevisionGlobalId: "",
    fileOptimisticVersion: "1",
    frappeContentHash: "",
    sha256: "",
  };
}

function emptyConfirmationDraft(): ConfirmationDraft {
  return {
    kind: "relationship",
    worksheetName: "",
    sourceRow: "",
    anchorKey: "",
    selectedTargetObject: "tooling_master",
    selectedTargetGlobalId: "",
    selectedTargetSnapshotHash: "",
    reason: "",
  };
}

function LoadingSurface(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section
      aria-busy="true"
      aria-label={t("Loading Tooling List import workspace")}
      className="workspace-resource-state workspace-resource-state--loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">
        {t("Loading Tooling List import workspace")}
      </span>
    </section>
  );
}

export default function ToolingImportWorkspace({
  dataSource,
  projectId,
  navigate,
  reportWorkspaceDirty,
}: {
  dataSource: ToolingImportDataSource;
  projectId: string;
  navigate: (target: string) => void;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [collection, setCollection] = useState<
    ResourceState<ToolingImportBatchCollection>
  >({ kind: "loading" });
  const [detail, setDetail] = useState<
    ResourceState<ToolingImportBatchDetail> | { kind: "idle" }
  >({ kind: "idle" });
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState<ImportStep>("upload");
  const [sourceDraft, setSourceDraft] = useState<SourceDraft>(emptySourceDraft);
  const [mappingDraft, setMappingDraft] = useState<MappingDraft>({
    templateKey: "synthetic-tooling-list.v1",
    reason: "",
  });
  const [confirmationDraft, setConfirmationDraft] = useState<ConfirmationDraft>(
    emptyConfirmationDraft,
  );
  const [correctionDraft, setCorrectionDraft] = useState<CorrectionDraft>({
    worksheetName: "",
    sourceRow: "",
    sourceHeader: "",
    correctedValue: "",
  });
  const [correctionArtifact, setCorrectionArtifact] =
    useState<ToolingImportCorrectionArtifact | null>(null);
  const [rollbackEligibility, setRollbackEligibility] =
    useState<ToolingImportReconciliationRevision | null>(null);
  const [previewReviewed, setPreviewReviewed] = useState(false);
  const [rollbackReviewOpen, setRollbackReviewOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const latestCommand = useRef<(() => void) | null>(null);
  const commandController = useRef<AbortController | null>(null);
  const dirtyReturnFocus = useRef<HTMLElement | null>(null);
  const loadedDetail = detail.kind === "loaded" ? detail.value : null;
  const inspection = last(loadedDetail?.inspections ?? []);
  const mapping = last(loadedDetail?.mappingProposals ?? []);
  const preview = last(loadedDetail?.previews ?? []);
  const job = last(loadedDetail?.jobs ?? []);

  const loadDetail = useCallback(
    (batchId: string): void => {
      const controller = new AbortController();
      setDetail({ kind: "loading" });
      void dataSource
        .loadBatch(projectId, batchId, controller.signal)
        .then((value) => {
          if (!controller.signal.aborted) setDetail({ kind: "loaded", value });
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            error instanceof ToolingRequestCancelledError
          )
            return;
          setDetail({ kind: "failed", failure: toRequestFailure(error) });
        });
    },
    [dataSource, projectId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void dataSource
      .loadBatches(projectId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setCollection({ kind: "loaded", value });
        const selected = value.batches[0] ?? null;
        setSelectedBatchId(selected?.batchGlobalId ?? null);
        if (selected) loadDetail(selected.batchGlobalId);
        else setDetail({ kind: "idle" });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ToolingRequestCancelledError
        )
          return;
        setCollection({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, loadDetail, projectId]);

  useEffect(() => {
    if (!job || (job.state !== "queued" && job.state !== "processing"))
      return undefined;
    const controller = new AbortController();
    const timeout = globalThis.setTimeout(() => {
      void dataSource
        .loadJob(projectId, job.batchGlobalId, job.globalId, controller.signal)
        .then((nextJob) => {
          if (controller.signal.aborted) return;
          setDetail((current) =>
            current.kind === "loaded"
              ? {
                  kind: "loaded",
                  value: {
                    ...current.value,
                    jobs: [
                      ...current.value.jobs.filter(
                        (item) => item.globalId !== nextJob.globalId,
                      ),
                      nextJob,
                    ],
                  },
                }
              : current,
          );
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            error instanceof ToolingRequestCancelledError
          )
            return;
          setCommand({ kind: "failed", failure: toRequestFailure(error) });
        });
    }, 1200);
    return () => {
      globalThis.clearTimeout(timeout);
      controller.abort();
    };
  }, [dataSource, job, projectId]);

  useEffect(
    () => () => {
      commandController.current?.abort();
    },
    [],
  );

  const isDirty = useMemo(
    () =>
      Boolean(
        sourceDraft.customerScopeId.trim() ||
        sourceDraft.fileRevisionGlobalId.trim() ||
        sourceDraft.frappeContentHash.trim() ||
        sourceDraft.sha256.trim() ||
        sourceDraft.fileOptimisticVersion.trim() !== "1" ||
        mappingDraft.reason.trim() ||
        confirmationDraft.worksheetName.trim() ||
        confirmationDraft.sourceRow.trim() ||
        confirmationDraft.anchorKey.trim() ||
        confirmationDraft.selectedTargetGlobalId.trim() ||
        confirmationDraft.selectedTargetSnapshotHash.trim() ||
        confirmationDraft.reason.trim() ||
        correctionDraft.worksheetName.trim() ||
        correctionDraft.sourceRow.trim() ||
        correctionDraft.sourceHeader.trim() ||
        correctionDraft.correctedValue.trim(),
      ),
    [confirmationDraft, correctionDraft, mappingDraft.reason, sourceDraft],
  );

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!isDirty) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: selectedBatchId ?? `${projectId}:new-tooling-import`,
      returnFocusTarget: () => dirtyReturnFocus.current,
      version: "unsaved-tooling-import-context",
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [isDirty, projectId, reportWorkspaceDirty, selectedBatchId]);

  const runCommand = useCallback(
    (
      label: string,
      _prefix: string,
      operation: (
        signal: AbortSignal,
        context: NonNullable<typeof sessionCommandContext>,
      ) => Promise<void>,
    ): void => {
      if (!sessionCommandContext) return;
      const execute = (): void => {
        commandController.current?.abort();
        const controller = new AbortController();
        commandController.current = controller;
        setCommand({ kind: "processing", label });
        setFormError(null);
        void operation(controller.signal, sessionCommandContext)
          .then(() => {
            if (!controller.signal.aborted) setCommand({ kind: "idle" });
          })
          .catch((error: unknown) => {
            if (
              controller.signal.aborted ||
              error instanceof ToolingRequestCancelledError
            )
              return;
            setCommand({ kind: "failed", failure: toRequestFailure(error) });
          });
      };
      latestCommand.current = execute;
      execute();
    },
    [sessionCommandContext],
  );

  const contextFor = useCallback(
    (
      prefix: string,
      signal: AbortSignal,
      session: NonNullable<typeof sessionCommandContext>,
    ) => ({
      ...session,
      idempotencyKey: `${prefix}-${globalThis.crypto.randomUUID()}`,
      signal,
    }),
    [],
  );

  const replaceJob = useCallback((nextJob: ToolingImportJobSnapshot): void => {
    const failedRow = nextJob.rowResults.find(
      (row) => row.state === "failed_retryable",
    );
    const failedField = failedRow?.fieldResults[0];
    if (failedRow && failedField) {
      setCorrectionDraft({
        correctedValue: "",
        sourceHeader: failedField.sourceHeader,
        sourceRow: String(failedRow.sourceRow),
        worksheetName: failedRow.worksheetName,
      });
    }
    setDetail((current) =>
      current.kind === "loaded"
        ? {
            kind: "loaded",
            value: {
              ...current.value,
              jobs: [
                ...current.value.jobs.filter(
                  (item) => item.globalId !== nextJob.globalId,
                ),
                nextJob,
              ],
            },
          }
        : current,
    );
  }, []);

  const registerSource = (): void => {
    if (
      !sourceDraft.customerScopeId.trim() ||
      !sourceDraft.fileRevisionGlobalId.trim() ||
      !sourceDraft.frappeContentHash.trim() ||
      !sourceDraft.sha256.trim()
    ) {
      setFormError(t("Enter every required registered workbook reference."));
      return;
    }
    runCommand(
      t("Registering the controlled workbook"),
      "tooling-import-register",
      async (signal, session) => {
        const batch = await dataSource.registerSource(
          projectId,
          {
            customerScopeId: sourceDraft.customerScopeId.trim(),
            fileRevisionGlobalId: sourceDraft.fileRevisionGlobalId.trim(),
            fileOptimisticVersion: Number(sourceDraft.fileOptimisticVersion),
            frappeContentHash: sourceDraft.frappeContentHash.trim(),
            sha256: sourceDraft.sha256.trim(),
          },
          contextFor("tooling-import-register", signal, session),
        );
        setSelectedBatchId(batch.batchGlobalId);
        setCollection((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  batches: [...current.value.batches, batch],
                },
              }
            : current,
        );
        setSourceDraft(emptySourceDraft());
        setActiveStep("detect");
        loadDetail(batch.batchGlobalId);
      },
    );
  };

  const inspectSource = (): void => {
    if (!loadedDetail) return;
    runCommand(
      t("Inspecting workbook structure"),
      "tooling-import-inspect",
      async (signal, session) => {
        const next = await dataSource.inspect(
          projectId,
          loadedDetail.batch.batchGlobalId,
          contextFor("tooling-import-inspect", signal, session),
        );
        setDetail((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  inspections: [...current.value.inspections, next],
                },
              }
            : current,
        );
        setActiveStep("map");
      },
    );
  };

  const createMapping = (): void => {
    if (!loadedDetail || !inspection || !mappingDraft.reason.trim()) {
      setFormError(t("Enter a reason for the mapping proposal."));
      return;
    }
    runCommand(
      t("Creating a mapping proposal"),
      "tooling-import-map",
      async (signal, session) => {
        const next = await dataSource.createMappingProposal(
          projectId,
          loadedDetail.batch.batchGlobalId,
          {
            inspectionGlobalId: inspection.globalId,
            inspectionSnapshotHash: inspection.snapshotHash,
            templateKey: mappingDraft.templateKey,
            reason: mappingDraft.reason.trim(),
          },
          contextFor("tooling-import-map", signal, session),
        );
        setDetail((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  mappingProposals: [...current.value.mappingProposals, next],
                },
              }
            : current,
        );
        setMappingDraft((current) => ({ ...current, reason: "" }));
        setActiveStep("transform");
      },
    );
  };

  const createPreview = (): void => {
    if (!loadedDetail || !inspection || !mapping) return;
    runCommand(
      t("Transforming and validating workbook rows"),
      "tooling-import-preview",
      async (signal, session) => {
        const next = await dataSource.createPreview(
          projectId,
          loadedDetail.batch.batchGlobalId,
          {
            inspectionGlobalId: inspection.globalId,
            inspectionSnapshotHash: inspection.snapshotHash,
            mappingGlobalId: mapping.globalId,
            mappingSnapshotHash: mapping.snapshotHash,
          },
          contextFor("tooling-import-preview", signal, session),
        );
        const requiredRow = next.rows.find((row) => row.requiresConfirmation);
        const ambiguousAnchor = inspection.imageAnchors.find(
          (anchor) => anchor.requiresConfirmation,
        );
        setConfirmationDraft({
          ...emptyConfirmationDraft(),
          worksheetName: requiredRow?.worksheetName ?? "",
          sourceRow: requiredRow ? String(requiredRow.sourceRow) : "",
          anchorKey: ambiguousAnchor?.anchorKey ?? "",
        });
        setDetail((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  previews: [...current.value.previews, next],
                },
              }
            : current,
        );
        setPreviewReviewed(false);
        setActiveStep("validate");
      },
    );
  };

  const confirmPreview = (): void => {
    if (
      !loadedDetail ||
      !preview ||
      !confirmationDraft.worksheetName.trim() ||
      !confirmationDraft.sourceRow.trim() ||
      !confirmationDraft.selectedTargetGlobalId.trim() ||
      !confirmationDraft.selectedTargetSnapshotHash.trim() ||
      !confirmationDraft.reason.trim()
    ) {
      setFormError(t("Enter every required confirmation value."));
      return;
    }
    runCommand(
      t("Confirming the immutable preview"),
      "tooling-import-confirm",
      async (signal, session) => {
        const next = await dataSource.confirmPreview(
          projectId,
          loadedDetail.batch.batchGlobalId,
          preview.previewGlobalId,
          {
            expectedVersion: preview.previewVersion,
            expectedSnapshotHash: preview.snapshotHash,
            confirmations: [
              {
                kind: confirmationDraft.kind,
                worksheetName: confirmationDraft.worksheetName.trim(),
                sourceRow: Number(confirmationDraft.sourceRow),
                ...(confirmationDraft.anchorKey.trim()
                  ? { anchorKey: confirmationDraft.anchorKey.trim() }
                  : {}),
                selectedTargetObject: confirmationDraft.selectedTargetObject,
                selectedTargetGlobalId:
                  confirmationDraft.selectedTargetGlobalId.trim(),
                selectedTargetSnapshotHash:
                  confirmationDraft.selectedTargetSnapshotHash.trim(),
                reason: confirmationDraft.reason.trim(),
              },
            ],
          },
          contextFor("tooling-import-confirm", signal, session),
        );
        setDetail((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  previews: [...current.value.previews, next],
                },
              }
            : current,
        );
        setConfirmationDraft(emptyConfirmationDraft());
        setPreviewReviewed(false);
      },
    );
  };

  const executePreview = (): void => {
    if (
      !loadedDetail ||
      !preview ||
      !preview.executionEligible ||
      !previewReviewed
    )
      return;
    runCommand(
      t("Queuing the exact preview for import"),
      "tooling-import-execute",
      async (signal, session) => {
        const next = await dataSource.execute(
          projectId,
          loadedDetail.batch.batchGlobalId,
          preview.previewGlobalId,
          {
            expectedVersion: preview.previewVersion,
            expectedSnapshotHash: preview.snapshotHash,
          },
          contextFor("tooling-import-execute", signal, session),
        );
        replaceJob(next);
        setActiveStep("execute");
      },
    );
  };

  const createCorrection = (): void => {
    if (
      !loadedDetail ||
      !job ||
      !correctionDraft.worksheetName.trim() ||
      !correctionDraft.sourceRow.trim() ||
      !correctionDraft.sourceHeader.trim() ||
      !correctionDraft.correctedValue.trim()
    ) {
      setFormError(t("Enter the exact failed field and its corrected value."));
      return;
    }
    runCommand(
      t("Creating a controlled correction file"),
      "tooling-import-correction",
      async (signal, session) => {
        const artifact = await dataSource.createCorrectionArtifact(
          projectId,
          loadedDetail.batch.batchGlobalId,
          job.globalId,
          {
            expectedVersion: job.optimisticVersion,
            expectedSnapshotHash: job.snapshotHash,
            corrections: [
              {
                worksheetName: correctionDraft.worksheetName.trim(),
                sourceRow: Number(correctionDraft.sourceRow),
                sourceHeader: correctionDraft.sourceHeader.trim(),
                correctedValue: correctionDraft.correctedValue,
              },
            ],
          },
          contextFor("tooling-import-correction", signal, session),
        );
        setCorrectionArtifact(artifact);
      },
    );
  };

  const downloadCorrection = (): void => {
    if (!loadedDetail || !job || !correctionArtifact || !sessionCommandContext)
      return;
    runCommand(
      t("Downloading the controlled correction file"),
      "tooling-import-correction-download",
      async (signal, session) => {
        const downloaded = await dataSource.downloadCorrectionArtifact(
          projectId,
          loadedDetail.batch.batchGlobalId,
          job.globalId,
          correctionArtifact,
          contextFor("tooling-import-correction-download", signal, session),
        );
        const url = URL.createObjectURL(downloaded.blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = downloaded.fileName;
        anchor.click();
        URL.revokeObjectURL(url);
      },
    );
  };

  const retryFailedRows = (): void => {
    if (!loadedDetail || !job || !correctionArtifact) return;
    runCommand(
      t("Retrying exact failed rows"),
      "tooling-import-retry",
      async (signal, session) => {
        const next = await dataSource.retry(
          projectId,
          loadedDetail.batch.batchGlobalId,
          job.globalId,
          {
            expectedVersion: job.optimisticVersion,
            expectedSnapshotHash: job.snapshotHash,
            correctionArtifactGlobalId: correctionArtifact.globalId,
            correctionArtifactSnapshotHash: correctionArtifact.snapshotHash,
          },
          contextFor("tooling-import-retry", signal, session),
        );
        replaceJob(next);
        setCorrectionArtifact(null);
        setCorrectionDraft((current) => ({ ...current, correctedValue: "" }));
      },
    );
  };

  const reconcile = (): void => {
    if (!loadedDetail || !job) return;
    runCommand(
      t("Reconciling imported targets"),
      "tooling-import-reconcile",
      async (signal, session) => {
        const next = await dataSource.reconcile(
          projectId,
          loadedDetail.batch.batchGlobalId,
          job.globalId,
          {
            expectedVersion: job.optimisticVersion,
            expectedSnapshotHash: job.snapshotHash,
          },
          contextFor("tooling-import-reconcile", signal, session),
        );
        setDetail((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  jobs: current.value.jobs.map((item) =>
                    item.globalId === job.globalId
                      ? {
                          ...item,
                          reconciliations: [
                            ...(item.reconciliations ?? []),
                            next,
                          ],
                        }
                      : item,
                  ),
                },
              }
            : current,
        );
      },
    );
  };

  const evaluateRollback = (): void => {
    if (!loadedDetail || !job) return;
    runCommand(
      t("Evaluating rollback eligibility"),
      "tooling-import-rollback-evaluate",
      async (signal, session) => {
        const next = await dataSource.evaluateRollback(
          projectId,
          loadedDetail.batch.batchGlobalId,
          job.globalId,
          {
            expectedVersion: job.optimisticVersion,
            expectedSnapshotHash: job.snapshotHash,
          },
          contextFor("tooling-import-rollback-evaluate", signal, session),
        );
        setRollbackEligibility(next);
      },
    );
  };

  const rollback = (): void => {
    setRollbackReviewOpen(false);
    if (!loadedDetail || !job || !rollbackEligibility) return;
    runCommand(
      t("Rolling back eligible imported targets"),
      "tooling-import-rollback",
      async (signal, session) => {
        const result = await dataSource.rollback(
          projectId,
          loadedDetail.batch.batchGlobalId,
          job.globalId,
          {
            expectedVersion: job.optimisticVersion,
            expectedSnapshotHash: job.snapshotHash,
            eligibilityGlobalId: rollbackEligibility.globalId,
            eligibilitySnapshotHash: rollbackEligibility.snapshotHash,
          },
          contextFor("tooling-import-rollback", signal, session),
        );
        replaceJob(result.job);
        setRollbackEligibility(null);
      },
    );
  };

  if (collection.kind === "loading") return <LoadingSurface />;
  if (collection.kind === "failed") {
    return (
      <article className="page page--object tooling-import">
        <Panel title={t("Tooling List import unavailable")}>
          <RequestFailurePanel failure={collection.failure} />
          <div className="tooling-import__actions">
            {canRetryFailure(collection.failure) ? (
              <Button
                onClick={() => {
                  setCollection({ kind: "loading" });
                  setAttempt((value) => value + 1);
                }}
              >
                {t("Retry")}
              </Button>
            ) : null}
            <Button
              onClick={() => {
                navigate(`/projects/${projectId}/tooling`);
              }}
            >
              {t("Return to Tooling cockpit")}
            </Button>
          </div>
        </Panel>
      </article>
    );
  }

  const currentCollection = collection.value;
  const processing = command.kind === "processing";
  const canCommand = sessionCommandContext !== null && !processing;
  const jobRetryable =
    job?.state === "partially_succeeded" || job?.state === "failed_retryable";
  const findings =
    preview?.rows.flatMap((row) =>
      row.fields.flatMap((field) =>
        field.findings.map((finding) => ({ row, field, finding })),
      ),
    ) ?? [];
  const failureResults =
    job?.rowResults.flatMap((row) =>
      row.fieldResults.map((field) => ({ row, field })),
    ) ?? [];
  const reconciliations = job?.reconciliations ?? [];
  const rollbackDenied =
    rollbackEligibility?.items.some(
      (item) => item.state === "changed" || item.state === "downstream_used",
    ) ?? false;

  return (
    <article className="page page--object tooling-import">
      <ObjectHeader
        code={t("Tooling List import")}
        metadata={
          <span>
            {t("Selected Project")}:{" "}
            <span data-language-exempt="identifier">{projectId}</span>
            {selectedBatchId ? (
              <>
                {" · "}
                {t("Batch")}:{" "}
                <span data-language-exempt="identifier">{selectedBatchId}</span>
              </>
            ) : null}
          </span>
        }
        name={t("Controlled workbook worker workspace")}
        nameIsBusinessData={false}
        secondaryAction={
          <Button
            icon="collapse"
            onClick={() => {
              navigate(`/projects/${projectId}/tooling`);
            }}
          >
            {t("Return to Tooling cockpit")}
          </Button>
        }
        source={source}
        status={
          <SemanticStatus
            label={t("Project-first import boundary")}
            tone="info"
          />
        }
      />

      {currentCollection.mappingAuthority.state === "unavailable" ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Production mapping is unavailable.")}</span>
          <span>
            {t(
              "Only approved synthetic fixture mappings can reach execution in this checkpoint.",
            )}
          </span>
        </div>
      ) : (
        <div
          className="scenario-banner scenario-banner--processing"
          role="status"
        >
          <span>{t("Approved synthetic fixture mapping is active.")}</span>
          <span>{t("Production mapping activation remains disabled.")}</span>
        </div>
      )}

      {!sessionCommandContext ? (
        <div
          className="scenario-banner scenario-banner--read-only"
          role="status"
        >
          <span>{t("Tooling List import is read only in this session.")}</span>
          <span>
            {t(
              "Session verification is required before a command can be submitted.",
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
            {t("The exact command is processing. Keep this workspace open.")}
          </span>
        </div>
      ) : null}
      {command.kind === "failed" ? (
        <div className="tooling-import__command-failure">
          <RequestFailurePanel failure={command.failure} />
          {canRetryFailure(command.failure) ? (
            <Button
              disabled={processing}
              onClick={() => latestCommand.current?.()}
            >
              {t("Retry exact command")}
            </Button>
          ) : null}
        </div>
      ) : null}
      {formError ? (
        <div className="form-error" role="alert">
          {formError}
        </div>
      ) : null}

      <MetricStrip
        className="tooling-import__metrics"
        metrics={[
          {
            label: t("Registered batches"),
            value: formatNumber(locale, currentCollection.batches.length, 0),
          },
          {
            label: t("Preview rows"),
            value: formatNumber(locale, preview?.rows.length ?? 0, 0),
          },
          {
            label: t("Created"),
            value: formatNumber(locale, job?.counts.created ?? 0, 0),
          },
          {
            label: t("Retryable failures"),
            value: formatNumber(locale, job?.counts.failed_retryable ?? 0, 0),
            tone: job?.counts.failed_retryable ? "warning" : "neutral",
          },
        ]}
      />

      <div className="tooling-import__layout">
        <nav
          aria-label={t("Tooling import steps")}
          className="tooling-import__rail"
        >
          <ol>
            {steps.map((step, index) => (
              <li
                className={
                  index > 0 ? "tooling-import__rail-divider" : undefined
                }
                key={step}
              >
                <button
                  aria-current={activeStep === step ? "step" : undefined}
                  className="tooling-import__step"
                  onClick={() => {
                    setActiveStep(step);
                  }}
                  type="button"
                >
                  <span className="tooling-import__step-index">
                    {formatNumber(locale, index + 1, 0)}
                  </span>
                  <span>{stepLabel(t, step)}</span>
                </button>
              </li>
            ))}
          </ol>
        </nav>

        <main className="tooling-import__workspace">
          {activeStep === "upload" ? (
            <Panel title={t("1. Register controlled workbook")}>
              <p>
                {t(
                  "Register an existing private Frappe File revision. The browser does not upload or parse the workbook.",
                )}
              </p>
              <div className="tooling-import__form-grid">
                <label className="field-control">
                  <span>{t("Customer scope")}</span>
                  <TextInput
                    disabled={
                      !currentCollection.permissions.registerSource ||
                      processing
                    }
                    maxLength={128}
                    onChange={(event) => {
                      const value = event.currentTarget.value;
                      setSourceDraft((current) => ({
                        ...current,
                        customerScopeId: value,
                      }));
                    }}
                    ref={(element) => {
                      dirtyReturnFocus.current = element;
                    }}
                    required
                    value={sourceDraft.customerScopeId}
                  />
                </label>
                <label className="field-control">
                  <span>{t("File Revision identity")}</span>
                  <TextInput
                    disabled={
                      !currentCollection.permissions.registerSource ||
                      processing
                    }
                    onChange={(event) => {
                      const value = event.currentTarget.value;
                      setSourceDraft((current) => ({
                        ...current,
                        fileRevisionGlobalId: value,
                      }));
                    }}
                    required
                    value={sourceDraft.fileRevisionGlobalId}
                  />
                </label>
                <label className="field-control">
                  <span>{t("File optimistic version")}</span>
                  <TextInput
                    disabled={
                      !currentCollection.permissions.registerSource ||
                      processing
                    }
                    min={1}
                    onChange={(event) => {
                      const value = event.currentTarget.value;
                      setSourceDraft((current) => ({
                        ...current,
                        fileOptimisticVersion: value,
                      }));
                    }}
                    required
                    type="number"
                    value={sourceDraft.fileOptimisticVersion}
                  />
                </label>
                <label className="field-control">
                  <span>{t("Frappe content hash")}</span>
                  <TextInput
                    disabled={
                      !currentCollection.permissions.registerSource ||
                      processing
                    }
                    onChange={(event) => {
                      const value = event.currentTarget.value;
                      setSourceDraft((current) => ({
                        ...current,
                        frappeContentHash: value,
                      }));
                    }}
                    required
                    value={sourceDraft.frappeContentHash}
                  />
                </label>
                <label className="field-control tooling-import__form-wide">
                  <span>{t("SHA-256 digest")}</span>
                  <TextInput
                    disabled={
                      !currentCollection.permissions.registerSource ||
                      processing
                    }
                    maxLength={64}
                    onChange={(event) => {
                      const value = event.currentTarget.value;
                      setSourceDraft((current) => ({
                        ...current,
                        sha256: value,
                      }));
                    }}
                    required
                    value={sourceDraft.sha256}
                  />
                </label>
              </div>
              <div className="tooling-import__primary-action">
                <Button
                  disabled={
                    !canCommand || !currentCollection.permissions.registerSource
                  }
                  icon="upload"
                  onClick={registerSource}
                  visual="primary"
                >
                  {t("Register controlled workbook")}
                </Button>
              </div>
              {currentCollection.batches.length ? (
                <div className="table-scroll" tabIndex={0}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("Workbook")}</th>
                        <th>{t("Customer scope")}</th>
                        <th>{t("Registered at")}</th>
                        <th>{t("Batch")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentCollection.batches.map((batch) => (
                        <tr key={batch.batchGlobalId}>
                          <td>
                            <button
                              aria-pressed={
                                batch.batchGlobalId === selectedBatchId
                              }
                              className="tooling-import__batch-select"
                              data-language-exempt="business-data"
                              onClick={() => {
                                setSelectedBatchId(batch.batchGlobalId);
                                loadDetail(batch.batchGlobalId);
                              }}
                              type="button"
                            >
                              {batch.fileName}
                            </button>
                          </td>
                          <td data-language-exempt="business-data">
                            {batch.customerScopeId}
                          </td>
                          <td>
                            <time dateTime={batch.createdAt}>
                              {formatDateTime(locale, batch.createdAt)}
                            </time>
                          </td>
                          <td data-language-exempt="identifier">
                            {batch.batchGlobalId}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state" role="status">
                  <strong>
                    {t("No Tooling List import batch is registered.")}
                  </strong>
                  <span>
                    {t("Register one controlled workbook revision to begin.")}
                  </span>
                </div>
              )}
            </Panel>
          ) : null}

          {activeStep === "detect" ? (
            <Panel title={t("2. Detect workbook structure")}>
              {detail.kind === "loading" ? <LoadingSurface /> : null}
              {detail.kind === "failed" ? (
                <RequestFailurePanel failure={detail.failure} />
              ) : null}
              {loadedDetail && inspection ? (
                <>
                  <DefinitionList
                    rows={[
                      {
                        label: t("Worksheet"),
                        value: inspection.worksheetName,
                        exempt: "business-data",
                      },
                      {
                        label: t("Header row"),
                        value: formatNumber(locale, inspection.headerRow, 0),
                      },
                      {
                        label: t("Detected columns"),
                        value: formatNumber(
                          locale,
                          inspection.columns.length,
                          0,
                        ),
                      },
                      {
                        label: t("Detected regions"),
                        value: formatNumber(
                          locale,
                          inspection.regions.length,
                          0,
                        ),
                      },
                      {
                        label: t("Formula errors"),
                        value: formatNumber(
                          locale,
                          inspection.formulaErrors.length,
                          0,
                        ),
                      },
                      {
                        label: t("Image anchors"),
                        value: formatNumber(
                          locale,
                          inspection.imageAnchors.length,
                          0,
                        ),
                      },
                    ]}
                  />
                  <div className="table-scroll" tabIndex={0}>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("Header cell")}</th>
                          <th>{t("Source column")}</th>
                          <th>{t("Ordinal")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {inspection.columns.map((column) => (
                          <tr key={column.ordinal}>
                            <td data-language-exempt="identifier">
                              {column.headerCell}
                            </td>
                            <td data-language-exempt="business-data">
                              {column.sourceHeader}
                            </td>
                            <td>{formatNumber(locale, column.ordinal, 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : loadedDetail ? (
                <div className="empty-state" role="status">
                  <strong>
                    {t("Workbook structure has not been detected.")}
                  </strong>
                  <span>
                    {t("Detection is passive and creates an immutable report.")}
                  </span>
                </div>
              ) : (
                <p>{t("Select a registered batch before detection.")}</p>
              )}
              <div className="tooling-import__primary-action">
                <Button
                  disabled={!canCommand || !loadedDetail?.permissions.inspect}
                  icon="analysis"
                  onClick={inspectSource}
                  visual="primary"
                >
                  {t("Detect workbook structure")}
                </Button>
              </div>
            </Panel>
          ) : null}

          {activeStep === "map" ? (
            <Panel title={t("3. Propose field mapping")}>
              {!inspection ? (
                <p>
                  {t("Complete workbook detection before proposing a mapping.")}
                </p>
              ) : (
                <>
                  <div className="tooling-import__form-grid">
                    <label className="field-control">
                      <span>{t("Mapping template")}</span>
                      <TextInput disabled value={mappingDraft.templateKey} />
                    </label>
                    <label className="field-control tooling-import__form-wide">
                      <span>{t("Proposal reason")}</span>
                      <TextInput
                        disabled={
                          !loadedDetail?.permissions.createMappingProposal ||
                          processing
                        }
                        maxLength={1000}
                        onChange={(event) => {
                          const value = event.currentTarget.value;
                          setMappingDraft((current) => ({
                            ...current,
                            reason: value,
                          }));
                        }}
                        required
                        value={mappingDraft.reason}
                      />
                    </label>
                  </div>
                  {mapping ? (
                    <div className="table-scroll" tabIndex={0}>
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>{t("Source column")}</th>
                            <th>{t("Disposition")}</th>
                            <th>{t("Candidate object")}</th>
                            <th>{t("Candidate field")}</th>
                            <th>{t("Transformation")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {mapping.entries.map((entry) => (
                            <tr key={entry.sourceOrdinal}>
                              <td data-language-exempt="business-data">
                                {entry.sourceHeader}
                              </td>
                              <td>
                                {entry.disposition === "candidate"
                                  ? t("Candidate")
                                  : t("Unmapped")}
                              </td>
                              <td data-language-exempt="identifier">
                                {entry.targetObjectCandidate ??
                                  t("Not proposed")}
                              </td>
                              <td data-language-exempt="identifier">
                                {entry.targetFieldCandidate ??
                                  t("Not proposed")}
                              </td>
                              <td data-language-exempt="identifier">
                                {entry.transformationKey}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                  <div className="tooling-import__primary-action">
                    <Button
                      disabled={
                        !canCommand ||
                        !loadedDetail?.permissions.createMappingProposal
                      }
                      onClick={createMapping}
                      visual="primary"
                    >
                      {t("Create mapping proposal")}
                    </Button>
                  </div>
                </>
              )}
            </Panel>
          ) : null}

          {activeStep === "transform" ? (
            <Panel title={t("4. Transform rows")}>
              {mapping ? (
                <>
                  <DefinitionList
                    rows={[
                      {
                        label: t("Mapping state"),
                        value:
                          mapping.state === "approved_fixture"
                            ? t("Approved fixture")
                            : t("Proposal"),
                      },
                      {
                        label: t("Mapping version"),
                        value: formatNumber(locale, mapping.mappingVersion, 0),
                      },
                      {
                        label: t("Source signature"),
                        value: mapping.sourceSignature,
                        exempt: "identifier",
                      },
                      {
                        label: t("Mapping snapshot"),
                        value: mapping.snapshotHash,
                        exempt: "identifier",
                      },
                    ]}
                  />
                  <p>
                    {t(
                      "Transformation preserves raw values, normalized candidates and validation findings in one immutable preview.",
                    )}
                  </p>
                  <div className="tooling-import__primary-action">
                    <Button
                      disabled={
                        !canCommand || !loadedDetail?.permissions.createPreview
                      }
                      icon="play"
                      onClick={createPreview}
                      visual="primary"
                    >
                      {t("Transform and validate")}
                    </Button>
                  </div>
                </>
              ) : (
                <p>
                  {t("Create a mapping proposal before transforming rows.")}
                </p>
              )}
            </Panel>
          ) : null}

          {activeStep === "validate" ? (
            <Panel title={t("5. Validate findings")}>
              {preview ? (
                findings.length ? (
                  <div className="table-scroll" tabIndex={0}>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("Worksheet")}</th>
                          <th>{t("Row")}</th>
                          <th>{t("Source column")}</th>
                          <th>{t("Severity")}</th>
                          <th>{t("Finding")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {findings.map(({ row, field, finding }, index) => (
                          <tr
                            key={`${String(row.sourceRow)}-${String(field.sourceOrdinal)}-${String(index)}`}
                          >
                            <td data-language-exempt="business-data">
                              {row.worksheetName}
                            </td>
                            <td>{formatNumber(locale, row.sourceRow, 0)}</td>
                            <td data-language-exempt="business-data">
                              {field.sourceHeader}
                            </td>
                            <td>
                              <SemanticStatus
                                label={
                                  finding.severity === "warning"
                                    ? t("Warning")
                                    : finding.severity === "error"
                                      ? t("Error")
                                      : t("Confirmation required")
                                }
                                tone={
                                  finding.severity === "error"
                                    ? "danger"
                                    : "warning"
                                }
                              />
                            </td>
                            <td>{resultCodeLabel(t, finding.code)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-state" role="status">
                    <strong>
                      {t("No validation finding blocks this preview.")}
                    </strong>
                    <span>
                      {t("Review the immutable row preview before execution.")}
                    </span>
                  </div>
                )
              ) : (
                <p>
                  {t("Transform rows before reviewing validation findings.")}
                </p>
              )}
              <div className="tooling-import__primary-action">
                <Button
                  disabled={!preview}
                  onClick={() => {
                    setActiveStep("preview");
                  }}
                  visual="primary"
                >
                  {t("Review immutable preview")}
                </Button>
              </div>
            </Panel>
          ) : null}

          {activeStep === "preview" ? (
            <Panel title={t("6. Review immutable preview")}>
              {preview ? (
                <>
                  <div className="table-scroll" tabIndex={0}>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("Worksheet")}</th>
                          <th>{t("Row")}</th>
                          <th>{t("Action")}</th>
                          <th>{t("Raw value")}</th>
                          <th>{t("Normalized candidate")}</th>
                          <th>{t("Eligibility")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.rows.map((row) => (
                          <tr
                            key={`${row.worksheetName}-${String(row.sourceRow)}`}
                          >
                            <td data-language-exempt="business-data">
                              {row.worksheetName}
                            </td>
                            <td>{formatNumber(locale, row.sourceRow, 0)}</td>
                            <td>
                              {row.action === "create"
                                ? t("Create")
                                : row.action === "update"
                                  ? t("Update")
                                  : row.action === "skip"
                                    ? t("Skip")
                                    : t("Blocked")}
                            </td>
                            <td data-language-exempt="business-data">
                              {row.fields
                                .map((field) => field.rawValue)
                                .join(" · ")}
                            </td>
                            <td data-language-exempt="business-data">
                              {row.fields
                                .flatMap((field) => field.normalizedCandidates)
                                .join(" · ") || t("Not proposed")}
                            </td>
                            <td>
                              {row.requiresConfirmation
                                ? t("Confirmation required")
                                : t("Eligible")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {preview.rows.some((row) => row.requiresConfirmation) ? (
                    <div className="tooling-import__confirmation">
                      <h3>{t("Required confirmation")}</h3>
                      <div className="tooling-import__form-grid">
                        <label className="field-control">
                          <span>{t("Confirmation kind")}</span>
                          <Select
                            value={confirmationDraft.kind}
                            onChange={(event) => {
                              const value = event.currentTarget
                                .value as ConfirmationDraft["kind"];
                              setConfirmationDraft((current) => ({
                                ...current,
                                kind: value,
                              }));
                            }}
                          >
                            <option value="relationship">
                              {t("Relationship")}
                            </option>
                            <option value="image_anchor">
                              {t("Image anchor")}
                            </option>
                          </Select>
                        </label>
                        <label className="field-control">
                          <span>{t("Worksheet")}</span>
                          <TextInput
                            value={confirmationDraft.worksheetName}
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setConfirmationDraft((current) => ({
                                ...current,
                                worksheetName: value,
                              }));
                            }}
                          />
                        </label>
                        <label className="field-control">
                          <span>{t("Source row")}</span>
                          <TextInput
                            min={1}
                            type="number"
                            value={confirmationDraft.sourceRow}
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setConfirmationDraft((current) => ({
                                ...current,
                                sourceRow: value,
                              }));
                            }}
                          />
                        </label>
                        <label className="field-control">
                          <span>{t("Anchor key")}</span>
                          <TextInput
                            value={confirmationDraft.anchorKey}
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setConfirmationDraft((current) => ({
                                ...current,
                                anchorKey: value,
                              }));
                            }}
                          />
                        </label>
                        <label className="field-control">
                          <span>{t("Selected target object")}</span>
                          <Select
                            value={confirmationDraft.selectedTargetObject}
                            onChange={(event) => {
                              const value = event.currentTarget
                                .value as ConfirmationDraft["selectedTargetObject"];
                              setConfirmationDraft((current) => ({
                                ...current,
                                selectedTargetObject: value,
                              }));
                            }}
                          >
                            <option value="tooling_master">
                              {t("Tooling Master")}
                            </option>
                            <option value="part_revision">
                              {t("Part Revision")}
                            </option>
                          </Select>
                        </label>
                        <label className="field-control">
                          <span>{t("Target identity")}</span>
                          <TextInput
                            value={confirmationDraft.selectedTargetGlobalId}
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setConfirmationDraft((current) => ({
                                ...current,
                                selectedTargetGlobalId: value,
                              }));
                            }}
                          />
                        </label>
                        <label className="field-control tooling-import__form-wide">
                          <span>{t("Target snapshot hash")}</span>
                          <TextInput
                            value={confirmationDraft.selectedTargetSnapshotHash}
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setConfirmationDraft((current) => ({
                                ...current,
                                selectedTargetSnapshotHash: value,
                              }));
                            }}
                          />
                        </label>
                        <label className="field-control tooling-import__form-wide">
                          <span>{t("Reason")}</span>
                          <TextInput
                            maxLength={1000}
                            value={confirmationDraft.reason}
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setConfirmationDraft((current) => ({
                                ...current,
                                reason: value,
                              }));
                            }}
                          />
                        </label>
                      </div>
                      <div className="tooling-import__primary-action">
                        <Button
                          disabled={
                            !canCommand ||
                            !loadedDetail?.permissions.confirmPreview
                          }
                          onClick={confirmPreview}
                          visual="primary"
                        >
                          {t("Confirm preview relationship")}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <label className="tooling-import__review-check">
                        <input
                          checked={previewReviewed}
                          onChange={(event) => {
                            const checked = event.currentTarget.checked;
                            setPreviewReviewed(checked);
                          }}
                          type="checkbox"
                        />
                        <span>
                          {t(
                            "I reviewed the exact immutable preview and execution eligibility.",
                          )}
                        </span>
                      </label>
                      <div className="tooling-import__primary-action">
                        <Button
                          disabled={
                            !previewReviewed || !preview.executionEligible
                          }
                          onClick={() => {
                            setActiveStep("execute");
                          }}
                          visual="primary"
                        >
                          {t("Continue to execution")}
                        </Button>
                      </div>
                    </>
                  )}
                </>
              ) : (
                <p>{t("No immutable preview is available.")}</p>
              )}
            </Panel>
          ) : null}

          {activeStep === "execute" ? (
            <Panel title={t("7. Execute and recover")}>
              {!job && preview ? (
                <>
                  <p>
                    {preview.executionEligible
                      ? t("The reviewed preview is eligible for execution.")
                      : t("The preview is not eligible for execution.")}
                  </p>
                  <div className="tooling-import__primary-action">
                    <Button
                      disabled={
                        !canCommand ||
                        !preview.executionEligible ||
                        !previewReviewed ||
                        !loadedDetail?.permissions.execute
                      }
                      icon="play"
                      onClick={executePreview}
                      visual="primary"
                    >
                      {t("Execute exact preview")}
                    </Button>
                  </div>
                </>
              ) : null}
              {job ? (
                <>
                  <div className="tooling-import__result-strip">
                    <SemanticStatus
                      label={jobStateLabel(t, job.state)}
                      tone={jobTone(job.state)}
                    />
                    <span>
                      {t("Attempt")}: {formatNumber(locale, job.attempt, 0)}
                    </span>
                    <span>
                      {t("Updated")}:{" "}
                      <time dateTime={job.updatedAt}>
                        {formatDateTime(locale, job.updatedAt)}
                      </time>
                    </span>
                    <span>
                      {t("Trace ID")}:{" "}
                      <code data-language-exempt="identifier">
                        {job.failure?.traceId ??
                          job.rowResults[0]?.traceId ??
                          t("Not available")}
                      </code>
                    </span>
                  </div>
                  <MetricStrip
                    metrics={[
                      {
                        label: t("Created"),
                        value: formatNumber(locale, job.counts.created, 0),
                      },
                      {
                        label: t("Updated"),
                        value: formatNumber(locale, job.counts.updated, 0),
                      },
                      {
                        label: t("Skipped"),
                        value: formatNumber(locale, job.counts.skipped, 0),
                      },
                      {
                        label: t("Retryable failures"),
                        value: formatNumber(
                          locale,
                          job.counts.failed_retryable,
                          0,
                        ),
                        tone: job.counts.failed_retryable
                          ? "warning"
                          : "neutral",
                      },
                      {
                        label: t("Final failures"),
                        value: formatNumber(locale, job.counts.failed_final, 0),
                        tone: job.counts.failed_final ? "danger" : "neutral",
                      },
                    ]}
                  />
                  {job.state === "queued" || job.state === "processing" ? (
                    <div
                      aria-busy="true"
                      className="scenario-banner scenario-banner--processing"
                      role="status"
                    >
                      <span>{jobStateLabel(t, job.state)}</span>
                      <span>
                        {t(
                          "The worker result is polled from the exact job resource.",
                        )}
                      </span>
                    </div>
                  ) : null}
                  {failureResults.length ? (
                    <div className="table-scroll" tabIndex={0}>
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>{t("Row")}</th>
                            <th>{t("State")}</th>
                            <th>{t("Source column")}</th>
                            <th>{t("Result")}</th>
                            <th>{t("Target")}</th>
                            <th>{t("Trace ID")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {failureResults.map(({ row, field }) => (
                            <tr
                              key={`${row.globalId}-${String(field.sourceOrdinal)}`}
                            >
                              <td>{formatNumber(locale, row.sourceRow, 0)}</td>
                              <td>{rowStateLabel(t, row.state)}</td>
                              <td data-language-exempt="business-data">
                                {field.sourceHeader}
                              </td>
                              <td>{resultCodeLabel(t, field.resultCode)}</td>
                              <td data-language-exempt="identifier">
                                {row.targetGlobalId ?? t("Not created")}
                              </td>
                              <td data-language-exempt="identifier">
                                {row.traceId}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                  {jobRetryable ? (
                    <div className="tooling-import__correction">
                      <h3>{t("Correct and retry failed rows")}</h3>
                      <div className="tooling-import__form-grid">
                        <label className="field-control">
                          <span>{t("Worksheet")}</span>
                          <TextInput
                            value={correctionDraft.worksheetName}
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setCorrectionDraft((current) => ({
                                ...current,
                                worksheetName: value,
                              }));
                            }}
                          />
                        </label>
                        <label className="field-control">
                          <span>{t("Source row")}</span>
                          <TextInput
                            min={1}
                            type="number"
                            value={correctionDraft.sourceRow}
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setCorrectionDraft((current) => ({
                                ...current,
                                sourceRow: value,
                              }));
                            }}
                          />
                        </label>
                        <label className="field-control">
                          <span>{t("Source column")}</span>
                          <TextInput
                            value={correctionDraft.sourceHeader}
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setCorrectionDraft((current) => ({
                                ...current,
                                sourceHeader: value,
                              }));
                            }}
                          />
                        </label>
                        <label className="field-control">
                          <span>{t("Corrected value")}</span>
                          <TextInput
                            maxLength={32767}
                            value={correctionDraft.correctedValue}
                            onChange={(event) => {
                              const value = event.currentTarget.value;
                              setCorrectionDraft((current) => ({
                                ...current,
                                correctedValue: value,
                              }));
                            }}
                          />
                        </label>
                      </div>
                      {correctionArtifact ? (
                        <div className="tooling-import__artifact">
                          <DefinitionList
                            rows={[
                              {
                                label: t("Correction file"),
                                value: correctionArtifact.fileName,
                                exempt: "business-data",
                              },
                              {
                                label: t("Entries"),
                                value: formatNumber(
                                  locale,
                                  correctionArtifact.entryCount,
                                  0,
                                ),
                              },
                              {
                                label: t("SHA-256 digest"),
                                value: correctionArtifact.sha256,
                                exempt: "identifier",
                              },
                            ]}
                          />
                          <div className="tooling-import__actions">
                            <Button
                              disabled={
                                !loadedDetail?.permissions
                                  .downloadCorrectionArtifact
                              }
                              icon="document"
                              onClick={downloadCorrection}
                            >
                              {t("Download correction file")}
                            </Button>
                            <Button
                              disabled={
                                !canCommand || !loadedDetail?.permissions.retry
                              }
                              onClick={retryFailedRows}
                              visual="primary"
                            >
                              {t("Retry exact failed rows")}
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="tooling-import__primary-action">
                          <Button
                            disabled={
                              !canCommand ||
                              !loadedDetail?.permissions
                                .createCorrectionArtifact
                            }
                            onClick={createCorrection}
                            visual="primary"
                          >
                            {t("Create controlled correction file")}
                          </Button>
                        </div>
                      )}
                    </div>
                  ) : null}
                  {job.state !== "queued" &&
                  job.state !== "processing" &&
                  !jobRetryable ? (
                    <div className="tooling-import__primary-action">
                      <Button
                        onClick={() => {
                          setActiveStep("audit");
                        }}
                        visual="primary"
                      >
                        {t("Review audit and reconciliation")}
                      </Button>
                    </div>
                  ) : null}
                </>
              ) : null}
              {!job && !preview ? (
                <p>{t("Complete an immutable preview before execution.")}</p>
              ) : null}
            </Panel>
          ) : null}

          {activeStep === "audit" ? (
            <Panel title={t("8. Audit, reconcile and rollback")}>
              {job ? (
                <>
                  <DefinitionList
                    rows={[
                      {
                        label: t("Job identity"),
                        value: job.globalId,
                        exempt: "identifier",
                      },
                      {
                        label: t("Job state"),
                        value: jobStateLabel(t, job.state),
                      },
                      {
                        label: t("Snapshot hash"),
                        value: job.snapshotHash,
                        exempt: "identifier",
                      },
                      {
                        label: t("Queued at"),
                        value: formatDateTime(locale, job.queuedAt),
                      },
                      {
                        label: t("Updated at"),
                        value: formatDateTime(locale, job.updatedAt),
                      },
                    ]}
                  />
                  {reconciliations.length ? (
                    <div className="table-scroll" tabIndex={0}>
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>{t("Reconciliation kind")}</th>
                            <th>{t("Target")}</th>
                            <th>{t("State")}</th>
                            <th>{t("Downstream references")}</th>
                            <th>{t("Observed snapshot")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {reconciliations.flatMap((item) =>
                            item.items.map((entry) => (
                              <tr
                                key={`${item.globalId}-${entry.rowResultGlobalId}`}
                              >
                                <td>
                                  {item.kind === "reconciliation"
                                    ? t("Reconciliation")
                                    : item.kind === "rollback_eligibility"
                                      ? t("Rollback eligibility")
                                      : t("Rollback result")}
                                </td>
                                <td data-language-exempt="identifier">
                                  {entry.targetGlobalId}
                                </td>
                                <td>
                                  {reconciliationStateLabel(t, entry.state)}
                                </td>
                                <td>
                                  {formatNumber(
                                    locale,
                                    entry.downstreamReferenceCount,
                                    0,
                                  )}
                                </td>
                                <td data-language-exempt="identifier">
                                  {entry.observedSnapshotHash ?? t("Missing")}
                                </td>
                              </tr>
                            )),
                          )}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="empty-state" role="status">
                      <strong>
                        {t("No reconciliation revision is recorded.")}
                      </strong>
                      <span>
                        {t(
                          "Run reconciliation to compare imported targets with immutable execution truth.",
                        )}
                      </span>
                    </div>
                  )}
                  {rollbackEligibility ? (
                    <div
                      className={`scenario-banner ${rollbackDenied ? "scenario-banner--read-only" : "scenario-banner--processing"}`}
                      role="status"
                    >
                      <span>
                        {rollbackDenied
                          ? t(
                              "Rollback is denied by current target usage or changes.",
                            )
                          : t(
                              "Rollback is eligible for imported unused targets.",
                            )}
                      </span>
                      <span>
                        {t(
                          "The eligibility revision is immutable and bound to this job snapshot.",
                        )}
                      </span>
                    </div>
                  ) : null}
                  <div className="tooling-import__actions">
                    <Button
                      disabled={
                        !canCommand || !loadedDetail?.permissions.reconcile
                      }
                      onClick={reconcile}
                    >
                      {t("Reconcile imported targets")}
                    </Button>
                    {!rollbackEligibility ? (
                      <Button
                        disabled={
                          !canCommand ||
                          !loadedDetail?.permissions.evaluateRollback
                        }
                        onClick={evaluateRollback}
                        visual="primary"
                      >
                        {t("Evaluate rollback eligibility")}
                      </Button>
                    ) : !rollbackDenied ? (
                      <Button
                        disabled={
                          !canCommand || !loadedDetail?.permissions.rollback
                        }
                        onClick={() => {
                          setRollbackReviewOpen(true);
                        }}
                        visual="danger"
                      >
                        {t("Rollback imported unused objects")}
                      </Button>
                    ) : null}
                  </div>
                </>
              ) : (
                <p>{t("No execution job is available for audit.")}</p>
              )}
            </Panel>
          ) : null}
        </main>

        <DockedInspector title={t("Import truth inspector")}>
          {loadedDetail ? (
            <DefinitionList
              rows={[
                {
                  label: t("Workbook"),
                  value: loadedDetail.batch.fileName,
                  exempt: "business-data",
                },
                {
                  label: t("Customer scope"),
                  value: loadedDetail.batch.customerScopeId,
                  exempt: "business-data",
                },
                {
                  label: t("Batch identity"),
                  value: loadedDetail.batch.batchGlobalId,
                  exempt: "identifier",
                },
                {
                  label: t("Source snapshot"),
                  value: loadedDetail.batch.snapshotHash,
                  exempt: "identifier",
                },
                {
                  label: t("Inspection revisions"),
                  value: formatNumber(
                    locale,
                    loadedDetail.inspections.length,
                    0,
                  ),
                },
                {
                  label: t("Mapping revisions"),
                  value: formatNumber(
                    locale,
                    loadedDetail.mappingProposals.length,
                    0,
                  ),
                },
                {
                  label: t("Preview revisions"),
                  value: formatNumber(locale, loadedDetail.previews.length, 0),
                },
                {
                  label: t("Worker jobs"),
                  value: formatNumber(locale, loadedDetail.jobs.length, 0),
                },
              ]}
            />
          ) : (
            <p>
              {t(
                "Select or register a batch to inspect immutable import truth.",
              )}
            </p>
          )}
          {job ? (
            <div className="tooling-import__inspector-job">
              <h3>{t("Latest worker job")}</h3>
              <SemanticStatus
                label={jobStateLabel(t, job.state)}
                tone={jobTone(job.state)}
              />
              <code data-language-exempt="identifier">{job.globalId}</code>
            </div>
          ) : null}
        </DockedInspector>
      </div>

      {rollbackReviewOpen && job && rollbackEligibility ? (
        <ImpactReview
          confirmLabel={t("Rollback imported unused objects")}
          contextRows={[
            {
              label: t("Eligibility revision"),
              value: rollbackEligibility.globalId,
              exempt: "identifier",
            },
            {
              label: t("Eligible targets"),
              value: formatNumber(locale, rollbackEligibility.items.length, 0),
            },
          ]}
          details={{
            objectIdentity: job.globalId,
            version: `${String(job.optimisticVersion)} · ${job.snapshotHash}`,
            impact: t(
              "Only imported targets that are unchanged and unused downstream will be removed.",
            ),
            permission: t("Tooling import rollback permission is required."),
            irreversible: t(
              "The rollback creates an immutable result and cannot restore downstream edits.",
            ),
            failureHandling: t(
              "Denied or conflicted targets remain unchanged and are reported with a trace identifier.",
            ),
            audit: t(
              "The job and rollback result remain in the immutable import audit history.",
            ),
          }}
          onCancel={() => {
            setRollbackReviewOpen(false);
          }}
          onConfirm={rollback}
          reasonRequired={false}
          title={t("Confirm Tooling import rollback")}
        />
      ) : null}
    </article>
  );
}
