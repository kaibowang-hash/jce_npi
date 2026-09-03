import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  HistoricalMigrationDataSource,
  HistoricalMigrationFamily,
  HistoricalMigrationJob,
  HistoricalMigrationResult,
  HistoricalMigrationJobState,
  HistoricalMigrationPreview,
  HistoricalMigrationWorkspace as Workspace,
} from "../api/historical-migration-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { MetricStrip, ObjectHeader } from "../components/object-components";
import { ImpactReview, Panel, SemanticStatus } from "../components/primitives";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, TextInput } from "../ui-adapters/npi-ui";

type ResourceState =
  | { kind: "loading" }
  | { kind: "loaded"; value: Workspace }
  | { kind: "failed"; failure: RequestFailure };
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };
type Confirmation =
  | { kind: "execute"; preview: HistoricalMigrationPreview }
  | { kind: "rollback"; job: HistoricalMigrationJob };

const initialDraft = {
  tenantId: "",
  fileRevisionGlobalId: "",
  fileOptimisticVersion: "1",
  sha256: "",
};
const source = {
  editableIn: "NPI_ONE" as const,
  sourceSystem: "NPI_ONE" as const,
  syncState: "local" as const,
};

function stateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: HistoricalMigrationJobState,
): string {
  const labels: Record<HistoricalMigrationJobState, string> = {
    queued: t("Queued"),
    processing: t("Processing"),
    partially_succeeded: t("Partially succeeded"),
    succeeded: t("Succeeded"),
    failed_retryable: t("Retryable failure"),
    failed_final: t("Final failure"),
    reconciled: t("Reconciled"),
    rolled_back: t("Rolled back"),
    rollback_denied: t("Rollback denied"),
  };
  return labels[state];
}

function stateTone(
  state: HistoricalMigrationJobState,
): "neutral" | "info" | "success" | "warning" | "danger" {
  if (["succeeded", "reconciled", "rolled_back"].includes(state))
    return "success";
  if (["queued", "processing"].includes(state)) return "info";
  if (["partially_succeeded", "failed_retryable"].includes(state))
    return "warning";
  return "danger";
}

function actionLabel(
  t: ReturnType<typeof useI18n>["t"],
  action: "create" | "link" | "skip" | "blocked",
): string {
  if (action === "create") return t("Create");
  if (action === "link") return t("Link");
  if (action === "skip") return t("Skip");
  return t("Blocked");
}

function familyLabel(
  t: ReturnType<typeof useI18n>["t"],
  family: HistoricalMigrationFamily | "job",
): string {
  if (family === "project") return t("Project");
  if (family === "tooling_mapping") return t("Tooling mapping");
  if (family === "file_index") return t("File index");
  if (family === "npi_reference") return t("NPI reference");
  return t("Job");
}

function resultStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: HistoricalMigrationResult["state"],
): string {
  if (state === "created") return t("Created");
  if (state === "linked") return t("Linked");
  if (state === "skipped") return t("Skipped");
  if (state === "failed_retryable") return t("Retryable failure");
  if (state === "failed_final") return t("Final failure");
  if (state === "rolled_back") return t("Rolled back");
  return t("Rollback denied");
}

export default function HistoricalMigrationWorkspace({
  dataSource,
}: {
  dataSource: HistoricalMigrationDataSource;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const [draft, setDraft] = useState(initialDraft);
  const [selectedPreviewId, setSelectedPreviewId] = useState<string | null>(
    null,
  );
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const loadAbort = useRef<AbortController | null>(null);
  const commandAbort = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    loadAbort.current?.abort();
    const controller = new AbortController();
    loadAbort.current = controller;
    void dataSource.load(controller.signal).then(
      (value) => {
        if (!controller.signal.aborted) setResource({ kind: "loaded", value });
      },
      (error: unknown) => {
        if (!controller.signal.aborted)
          setResource({ kind: "failed", failure: toRequestFailure(error) });
      },
    );
  }, [dataSource]);

  const refresh = useCallback(() => {
    setResource({ kind: "loading" });
    load();
  }, [load]);

  useEffect(() => {
    load();
    return () => {
      loadAbort.current?.abort();
      commandAbort.current?.abort();
    };
  }, [load]);

  const workspace = resource.kind === "loaded" ? resource.value : null;
  const selectedPreview = useMemo(
    () =>
      workspace?.previews.find((item) => item.globalId === selectedPreviewId) ??
      workspace?.previews[0] ??
      null,
    [selectedPreviewId, workspace],
  );
  const selectedJob = useMemo(
    () =>
      workspace?.jobs.find((item) => item.globalId === selectedJobId) ??
      workspace?.jobs[0] ??
      null,
    [selectedJobId, workspace],
  );
  const selectedJobCompleted =
    selectedJob !== null &&
    !["queued", "processing", "rolled_back", "rollback_denied"].includes(
      selectedJob.state,
    );

  useEffect(() => {
    if (!selectedJob || !["queued", "processing"].includes(selectedJob.state))
      return;
    const timer = window.setTimeout(load, 1500);
    return () => {
      window.clearTimeout(timer);
    };
  }, [load, selectedJob]);

  const run = useCallback(
    async (
      label: string,
      operation: (signal: AbortSignal, idempotencyKey: string) => Promise<void>,
    ): Promise<void> => {
      if (!sessionCommandContext) return;
      commandAbort.current?.abort();
      const controller = new AbortController();
      commandAbort.current = controller;
      setCommand({ kind: "processing", label });
      try {
        await operation(
          controller.signal,
          `p9-05-${globalThis.crypto.randomUUID()}`,
        );
        if (!controller.signal.aborted) {
          setCommand({ kind: "idle" });
          load();
        }
      } catch (error) {
        if (!controller.signal.aborted)
          setCommand({ kind: "failed", failure: toRequestFailure(error) });
      }
    },
    [load, sessionCommandContext],
  );

  const context = useCallback(
    (signal: AbortSignal, idempotencyKey: string) => {
      if (!sessionCommandContext)
        throw new Error("Session command context is unavailable.");
      return {
        csrfToken: sessionCommandContext.csrfToken,
        idempotencyKey,
        signal,
      };
    },
    [sessionCommandContext],
  );

  const createPreview = (): void => {
    void run(t("Creating preview"), async (signal, idempotencyKey) => {
      const preview = await dataSource.createPreview(
        {
          tenantId: draft.tenantId.trim(),
          fileRevisionGlobalId: draft.fileRevisionGlobalId.trim(),
          fileOptimisticVersion: Number(draft.fileOptimisticVersion),
          sha256: draft.sha256.trim(),
        },
        context(signal, idempotencyKey),
      );
      setSelectedPreviewId(preview.globalId);
    });
  };

  const execute = (preview: HistoricalMigrationPreview): void => {
    void run(t("Queueing rehearsal"), async (signal, idempotencyKey) => {
      const job = await dataSource.execute(
        preview,
        context(signal, idempotencyKey),
      );
      setSelectedJobId(job.globalId);
    });
  };

  const operateOnJob = (
    label: string,
    operation: (
      job: HistoricalMigrationJob,
      signal: AbortSignal,
      key: string,
    ) => Promise<unknown>,
  ): void => {
    if (!selectedJob) return;
    void run(label, async (signal, key) => {
      await operation(selectedJob, signal, key);
    });
  };

  const downloadCorrection = (): void => {
    if (!selectedJob?.correction) return;
    void run(t("Downloading correction artifact"), async (signal, key) => {
      const result = await dataSource.downloadCorrection(
        selectedJob,
        context(signal, key),
      );
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.fileName;
      anchor.click();
      URL.revokeObjectURL(url);
    });
  };

  return (
    <article
      className="page page--reporting historical-migration"
      data-testid="historical-migration-workspace"
    >
      <ObjectHeader
        code={t("Administration")}
        name={t("Historical migration rehearsal")}
        nameIsBusinessData={false}
        metadata={t(
          "Validate and rehearse one exact historical bundle on an explicitly enabled non-production Site.",
        )}
        source={source}
        secondaryAction={
          <Button icon="refresh" onClick={refresh}>
            {t("Refresh")}
          </Button>
        }
        status={
          <SemanticStatus
            label={
              workspace?.executionEnabled
                ? t("Execution enabled")
                : t("Preview only")
            }
            tone={workspace?.executionEnabled ? "warning" : "neutral"}
          />
        }
      />
      {resource.kind === "loading" ? (
        <section aria-busy="true" className="state-surface">
          {t("Loading migration workspace")}
        </section>
      ) : null}
      {resource.kind === "failed" ? (
        <section className="state-surface" role="alert">
          <h2>{t("Migration workspace unavailable")}</h2>
          <RequestFailurePanel failure={resource.failure} />
          <Button icon="refresh" onClick={refresh}>
            {t("Retry")}
          </Button>
        </section>
      ) : null}
      {workspace ? (
        <>
          <MetricStrip
            metrics={[
              {
                label: t("Previews"),
                value: formatNumber(locale, workspace.previews.length),
              },
              {
                label: t("Jobs"),
                value: formatNumber(locale, workspace.jobs.length),
              },
              { label: t("Production contact"), value: t("No") },
              { label: t("Mode"), value: t("Non-production rehearsal") },
            ]}
          />
          <div className="historical-migration__grid">
            <Panel title={t("Source File Revision")}>
              <div className="historical-migration__form">
                <label className="field-control">
                  <span>{t("Tenant ID")}</span>
                  <TextInput
                    maxLength={128}
                    required
                    value={draft.tenantId}
                    onChange={(event) => {
                      setDraft({ ...draft, tenantId: event.target.value });
                    }}
                  />
                </label>
                <label className="field-control">
                  <span>{t("File Revision global ID")}</span>
                  <TextInput
                    maxLength={36}
                    required
                    value={draft.fileRevisionGlobalId}
                    onChange={(event) => {
                      setDraft({
                        ...draft,
                        fileRevisionGlobalId: event.target.value,
                      });
                    }}
                  />
                </label>
                <label className="field-control">
                  <span>{t("File Revision version")}</span>
                  <TextInput
                    inputMode="numeric"
                    required
                    value={draft.fileOptimisticVersion}
                    onChange={(event) => {
                      setDraft({
                        ...draft,
                        fileOptimisticVersion: event.target.value,
                      });
                    }}
                  />
                </label>
                <label className="field-control">
                  <span>{t("Bundle SHA-256")}</span>
                  <TextInput
                    maxLength={64}
                    required
                    value={draft.sha256}
                    onChange={(event) => {
                      setDraft({ ...draft, sha256: event.target.value });
                    }}
                  />
                </label>
                <Button
                  disabled={
                    !sessionCommandContext || command.kind === "processing"
                  }
                  icon="document"
                  onClick={createPreview}
                >
                  {t("Create immutable preview")}
                </Button>
              </div>
              <p className="historical-migration__note">
                {t(
                  "Only one clean private File Revision with the frozen ZIP schema is accepted. No production system is contacted.",
                )}
              </p>
            </Panel>
            <Panel title={t("Rehearsal history")}>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t("Type")}</th>
                      <th>{t("Identity")}</th>
                      <th>{t("State")}</th>
                      <th>{t("Updated")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {workspace.previews.map((preview) => (
                      <tr
                        key={preview.globalId}
                        aria-selected={
                          selectedPreview?.globalId === preview.globalId
                        }
                        onClick={() => {
                          setSelectedPreviewId(preview.globalId);
                        }}
                      >
                        <td>{t("Preview")}</td>
                        <td>
                          <code data-language-exempt="identifier">
                            {preview.globalId}
                          </code>
                        </td>
                        <td>
                          {preview.summary.blocked ? t("Blocked") : t("Ready")}
                        </td>
                        <td>{formatDateTime(locale, preview.createdAt)}</td>
                      </tr>
                    ))}
                    {workspace.jobs.map((job) => (
                      <tr
                        key={job.globalId}
                        aria-selected={selectedJob?.globalId === job.globalId}
                        onClick={() => {
                          setSelectedJobId(job.globalId);
                        }}
                      >
                        <td>{t("Job")}</td>
                        <td>
                          <code data-language-exempt="identifier">
                            {job.globalId}
                          </code>
                        </td>
                        <td>
                          <SemanticStatus
                            label={stateLabel(t, job.state)}
                            tone={stateTone(job.state)}
                          />
                        </td>
                        <td>{formatDateTime(locale, job.updatedAt)}</td>
                      </tr>
                    ))}
                    {!workspace.previews.length && !workspace.jobs.length ? (
                      <tr>
                        <td colSpan={4}>
                          {t("No migration rehearsals have been created.")}
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>
          {selectedPreview ? (
            <Panel
              title={t("Immutable preview")}
              actions={
                <Button
                  disabled={
                    !workspace.executionEnabled ||
                    selectedPreview.summary.blocked > 0 ||
                    !sessionCommandContext ||
                    command.kind === "processing"
                  }
                  icon="play"
                  onClick={() => {
                    setConfirmation({
                      kind: "execute",
                      preview: selectedPreview,
                    });
                  }}
                >
                  {t("Execute rehearsal")}
                </Button>
              }
            >
              <MetricStrip
                metrics={(["create", "link", "skip", "blocked"] as const).map(
                  (key) => ({
                    label: actionLabel(t, key),
                    value: formatNumber(locale, selectedPreview.summary[key]),
                  }),
                )}
              />
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t("Family")}</th>
                      <th>{t("Source key")}</th>
                      <th>{t("Action")}</th>
                      <th>{t("Differences")}</th>
                      <th>{t("Findings")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedPreview.rows.map((row) => (
                      <tr key={`${row.family}-${row.sourceKey}`}>
                        <td>{familyLabel(t, row.family)}</td>
                        <td>
                          <code data-language-exempt="identifier">
                            {row.sourceKey}
                          </code>
                        </td>
                        <td>{actionLabel(t, row.action)}</td>
                        <td>
                          <span data-language-exempt="identifier">
                            {row.differences
                              .map((item) => item.field)
                              .join(", ") || "—"}
                          </span>
                        </td>
                        <td>
                          {row.findings.map((item) => item.message).join(" ") ||
                            "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="historical-migration__hash">
                {t("Snapshot hash")}:{" "}
                <code data-language-exempt="identifier">
                  {selectedPreview.snapshotHash}
                </code>
              </p>
            </Panel>
          ) : null}
          {selectedJob ? (
            <Panel
              title={t("Durable job")}
              actions={
                <div className="historical-migration__actions">
                  <Button
                    disabled={
                      !selectedJobCompleted ||
                      !sessionCommandContext ||
                      command.kind === "processing"
                    }
                    icon="refresh"
                    onClick={() => {
                      operateOnJob(t("Reconciling"), (job, signal, key) =>
                        dataSource.reconcile(job, context(signal, key)),
                      );
                    }}
                  >
                    {t("Reconcile")}
                  </Button>
                  <Button
                    icon="document"
                    disabled={
                      !sessionCommandContext ||
                      command.kind === "processing" ||
                      !selectedJob.results.some((item) =>
                        item.state.startsWith("failed_"),
                      )
                    }
                    onClick={() => {
                      operateOnJob(
                        t("Creating correction artifact"),
                        (job, signal, key) =>
                          dataSource.createCorrection(
                            job.globalId,
                            context(signal, key),
                          ),
                      );
                    }}
                  >
                    {t("Create correction artifact")}
                  </Button>
                  <Button
                    icon="document"
                    disabled={
                      !selectedJob.correction ||
                      !sessionCommandContext ||
                      command.kind === "processing"
                    }
                    onClick={downloadCorrection}
                  >
                    {t("Download correction artifact")}
                  </Button>
                  <Button
                    disabled={
                      !selectedJobCompleted ||
                      !sessionCommandContext ||
                      command.kind === "processing"
                    }
                    icon="history"
                    onClick={() => {
                      setConfirmation({ kind: "rollback", job: selectedJob });
                    }}
                  >
                    {t("Evaluate logical rollback")}
                  </Button>
                </div>
              }
            >
              <SemanticStatus
                label={stateLabel(t, selectedJob.state)}
                tone={stateTone(selectedJob.state)}
              />
              <p>
                {t(
                  "Targets are never deleted by this operation. Unsafe cases require forward correction.",
                )}
              </p>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t("Family")}</th>
                      <th>{t("Source key")}</th>
                      <th>{t("State")}</th>
                      <th>{t("Target")}</th>
                      <th>{t("Findings")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedJob.results.map((result) => (
                      <tr key={`${result.family}-${result.sourceKey}`}>
                        <td>{familyLabel(t, result.family)}</td>
                        <td>
                          <code data-language-exempt="identifier">
                            {result.sourceKey}
                          </code>
                        </td>
                        <td>{resultStateLabel(t, result.state)}</td>
                        <td>
                          <code data-language-exempt="identifier">
                            {result.targetGlobalId ?? "—"}
                          </code>
                        </td>
                        <td data-language-exempt="identifier">
                          {result.findingCodes?.join(", ") ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="historical-migration__hash">
                {t("Snapshot hash")}:{" "}
                <code data-language-exempt="identifier">
                  {selectedJob.snapshotHash}
                </code>
              </p>
            </Panel>
          ) : null}
        </>
      ) : null}
      {command.kind === "processing" ? (
        <div aria-live="polite" className="command-status">
          {command.label}
        </div>
      ) : null}
      {command.kind === "failed" ? (
        <section className="state-surface" role="alert">
          <h2>{t("Migration command failed")}</h2>
          <RequestFailurePanel failure={command.failure} />
        </section>
      ) : null}
      {confirmation ? (
        <ImpactReview
          title={
            confirmation.kind === "execute"
              ? t("Execute historical migration rehearsal")
              : t("Evaluate logical rollback")
          }
          confirmLabel={
            confirmation.kind === "execute"
              ? t("Queue exact preview")
              : t("Record rollback decision")
          }
          details={{
            objectIdentity:
              confirmation.kind === "execute"
                ? confirmation.preview.globalId
                : confirmation.job.globalId,
            version:
              confirmation.kind === "execute"
                ? String(confirmation.preview.version)
                : String(confirmation.job.optimisticVersion),
            impact:
              confirmation.kind === "execute"
                ? t(
                    "Creates or links only the rows frozen in this preview on the enabled non-production Site.",
                  )
                : t(
                    "Retains every target and changes only exact migration bindings when safe.",
                  ),
            permission: t("System Manager permission is required."),
            irreversible: t(
              "Created or referenced targets are never silently deleted.",
            ),
            failureHandling: t(
              "Partial and uncertain outcomes remain visible for correction and reconciliation.",
            ),
            audit: t(
              "Actor, exact version, hashes, request and trace are recorded.",
            ),
          }}
          onCancel={() => {
            setConfirmation(null);
          }}
          onConfirm={() => {
            const current = confirmation;
            setConfirmation(null);
            if (current.kind === "execute") execute(current.preview);
            else
              operateOnJob(t("Evaluating rollback"), (job, signal, key) =>
                dataSource.rollback(job, context(signal, key)),
              );
          }}
          returnFocusTarget={() => document.getElementById("main-content")}
        />
      ) : null}
    </article>
  );
}
