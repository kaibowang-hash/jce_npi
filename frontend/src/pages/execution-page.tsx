import { useState } from "react";

import type { ExecutionRow, Scenario, SyncState } from "../domain/view-models";
import { executionRows } from "../fixtures/prototype";
import { operationLabel, syncStateLabel } from "../i18n/copy";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
  SourceBadge,
  SyncBadge,
} from "../components/primitives";
import { MetricStrip } from "../components/object-components";

const executionRequestSource = {
  sourceSystem: "NPI_ONE" as const,
  editableIn: "NONE" as const,
  syncState: "failed_retryable" as const,
  lastSyncedAt: "2026-07-21T14:20:00Z",
};

type ReviewMode = "new" | "retry" | "reconcile" | null;

function stateTone(
  state: ExecutionRow["state"],
): "neutral" | "info" | "success" | "warning" | "danger" {
  if (state === "succeeded") return "success";
  if (state === "failed_final") return "danger";
  if (state === "failed_retryable" || state === "partial") return "warning";
  if (state === "processing" || state === "queued") return "info";
  return "neutral";
}

function sourceSyncState(state: ExecutionRow["state"]): SyncState {
  if (state === "succeeded") return "synced";
  if (state === "queued") return "pending";
  if (state === "cancelled") return "local";
  return state;
}

function executionCount(...states: readonly ExecutionRow["state"][]): number {
  return executionRows.filter((row) => states.includes(row.state)).length;
}

export default function ExecutionPage({
  scenario,
}: {
  scenario: Scenario;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const requestedId = new URLSearchParams(globalThis.location.search).get(
    "focus",
  );
  const [selectedId, setSelectedId] = useState(
    executionRows.some((row) => row.id === requestedId)
      ? (requestedId ?? "")
      : (executionRows[0]?.id ?? ""),
  );
  const [reviewMode, setReviewMode] = useState<ReviewMode>(null);
  const [mappingOpen, setMappingOpen] = useState(false);
  const [preparedOperation, setPreparedOperation] = useState<{
    mode: Exclude<ReviewMode, null>;
    reason: string;
  } | null>(null);
  const selected =
    executionRows.find((row) => row.id === selectedId) ?? executionRows[0];
  const retryable = selected?.state === "failed_retryable";
  const finalFailure = selected?.state === "failed_final";
  return (
    <article className="page page--execution">
      <header className="page-heading page-heading--actions">
        <div>
          <h1>{t("ERPNext Execution and Reconciliation")}</h1>
          <p>
            {t(
              "Engineering approval and ERPNext completion remain separate, traceable states.",
            )}
          </p>
        </div>
        <div>
          <Button
            disabled={scenario === "read_only"}
            onClick={() => {
              setReviewMode("reconcile");
            }}
          >
            {t("Run reconciliation")}
          </Button>
          <Button
            disabled={scenario === "read_only"}
            onClick={() => {
              setReviewMode("new");
            }}
            visual="primary"
          >
            {t("New execution request")}
          </Button>
        </div>
      </header>
      <MetricStrip
        metrics={[
          {
            label: t("Queued"),
            value: formatNumber(locale, executionCount("queued"), 0),
          },
          {
            label: t("Processing"),
            value: formatNumber(locale, executionCount("processing"), 0),
          },
          {
            label: t("Partially succeeded"),
            value: formatNumber(locale, executionCount("partial"), 0),
            tone: "warning",
          },
          {
            label: t("Failed, retry available"),
            value: formatNumber(locale, executionCount("failed_retryable"), 0),
            tone: "warning",
          },
          {
            label: t("Manual action required"),
            value: formatNumber(locale, executionCount("failed_final"), 0),
            tone: "danger",
          },
        ]}
      />
      {preparedOperation ? (
        <div className="scenario-banner scenario-banner--queued" role="status">
          <span>
            {preparedOperation.mode === "retry"
              ? t(
                  "Prototype retry command prepared. No request was queued in NPI One or ERPNext.",
                )
              : preparedOperation.mode === "reconcile"
                ? t(
                    "Prototype reconciliation prepared. No ERPNext or NPI One record was changed.",
                  )
                : t(
                    "Prototype execution command prepared. No request was queued in NPI One or ERPNext.",
                  )}
          </span>
          <span>
            {t(
              "The in-memory prototype command captured a reason; no audit record was persisted.",
            )}
          </span>
        </div>
      ) : null}
      <div className="execution-layout">
        <Panel title={t("Execution requests")}>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("Request number")}</th>
                  <th>{t("Business action")}</th>
                  <th>{t("Project or object")}</th>
                  <th>{t("Created")}</th>
                  <th>{t("Status")}</th>
                </tr>
              </thead>
              <tbody>
                {executionRows.map((row) => (
                  <tr
                    aria-selected={row.id === selected?.id}
                    className={
                      row.id === selected?.id ? "is-selected" : undefined
                    }
                    key={row.id}
                    onClick={() => {
                      setSelectedId(row.id);
                      setMappingOpen(false);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedId(row.id);
                        setMappingOpen(false);
                      }
                    }}
                    tabIndex={0}
                  >
                    <td data-language-exempt="identifier">
                      <strong>{row.id}</strong>
                    </td>
                    <td>{operationLabel(t, row.operationCode)}</td>
                    <td data-language-exempt="identifier">{row.context}</td>
                    <td>
                      <time dateTime={row.createdAt}>
                        {formatDateTime(locale, row.createdAt)}
                      </time>
                    </td>
                    <td>
                      <SemanticStatus
                        label={syncStateLabel(t, row.state)}
                        tone={stateTone(row.state)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <footer className="table-footer">
            <span>
              {t("Showing {{start}}–{{end}} of {{total}} items", {
                start: formatNumber(locale, 1, 0),
                end: formatNumber(locale, 6, 0),
                total: formatNumber(locale, executionRows.length, 0),
              })}
            </span>
            <Button disabled>{t("Next page")}</Button>
          </footer>
        </Panel>
        {selected ? (
          <Panel title={t("Execution request details")}>
            <div className="detail-heading">
              <h2 data-language-exempt="identifier">{selected.id}</h2>
              <SemanticStatus
                label={syncStateLabel(t, selected.state)}
                tone={stateTone(selected.state)}
              />
            </div>
            <DefinitionList
              rows={[
                {
                  label: t("Business action"),
                  value: operationLabel(t, selected.operationCode),
                },
                {
                  label: t("Source object"),
                  value: selected.context,
                  exempt: "identifier",
                },
                {
                  label: t("Target system"),
                  value: "ERPNext",
                  exempt: "business-data",
                },
                {
                  label: t("Request version"),
                  value: formatNumber(locale, 3, 0),
                },
                {
                  label: t("Idempotency key"),
                  value: `tool-asset:${selected.context}:v3`,
                  exempt: "identifier",
                },
                {
                  label: t("Last attempt"),
                  value: formatDateTime(locale, "2026-07-21T14:20:00Z"),
                },
                {
                  label: t("Trace ID"),
                  value: selected.traceId,
                  exempt: "identifier",
                },
              ]}
            />
            {retryable || finalFailure ? (
              <div className="failure-explanation">
                <SemanticStatus
                  label={
                    retryable
                      ? t("Failure reason")
                      : t("Manual action required")
                  }
                  tone={finalFailure ? "danger" : "warning"}
                />
                <p>
                  {t(
                    "ERPNext validation did not find an approved target asset category. No formal asset was written.",
                  )}
                </p>
                <small>
                  {retryable
                    ? t(
                        "Correct the mapping, review the impact, and then queue a safe retry with the same idempotency key.",
                      )
                    : t(
                        "This request reached a final failure. Correct the source data and prepare a new execution request.",
                      )}
                </small>
              </div>
            ) : null}
            <div className="inspector-badges">
              <SourceBadge
                source={{
                  ...executionRequestSource,
                  syncState: sourceSyncState(selected.state),
                }}
              />
              <SyncBadge state={selected.state} />
            </div>
            {retryable || finalFailure ? (
              <>
                <div className="detail-actions">
                  <Button
                    aria-controls="execution-field-mapping"
                    aria-expanded={mappingOpen}
                    onClick={() => {
                      setMappingOpen((current) => !current);
                    }}
                  >
                    {mappingOpen
                      ? t("Close field mapping")
                      : t("Open field mapping")}
                  </Button>
                  {retryable ? (
                    <Button
                      disabled={scenario === "read_only"}
                      onClick={() => {
                        setReviewMode("retry");
                      }}
                    >
                      {t("Review impact and retry")}
                    </Button>
                  ) : null}
                </div>
                {mappingOpen ? (
                  <section
                    aria-label={t("Field mapping preview")}
                    className="failure-explanation"
                    id="execution-field-mapping"
                  >
                    <h3>{t("Field mapping preview")}</h3>
                    <DefinitionList
                      rows={[
                        {
                          label: t("Source field"),
                          value: "tooling_acceptance.asset_category",
                          exempt: "identifier",
                        },
                        {
                          label: t("Target field"),
                          value: "Asset.asset_category",
                          exempt: "identifier",
                        },
                        {
                          label: t("Mapping result"),
                          value: t(
                            "No approved target value is available. Correct the governed mapping before preparing another request.",
                          ),
                        },
                      ]}
                    />
                  </section>
                ) : null}
              </>
            ) : null}
          </Panel>
        ) : null}
      </div>
      {reviewMode && (reviewMode !== "retry" || selected) ? (
        <ImpactReview
          confirmLabel={
            reviewMode === "retry"
              ? t("Queue safe retry")
              : reviewMode === "reconcile"
                ? t("Prepare reconciliation")
                : t("Prepare execution request")
          }
          details={
            reviewMode === "retry" && selected
              ? {
                  objectIdentity: selected.id,
                  version: `v3 · ${selected.context}`,
                  impact: t(
                    "Only the failed tool asset node will be retried. Completed ERPNext objects are unchanged.",
                  ),
                  permission: t("Integration operator permission is required."),
                  irreversible: t(
                    "ERPNext may create a formal object only after its own validation succeeds.",
                  ),
                  failureHandling: t(
                    "A failure remains visible and retryable or becomes a final failure with recovery guidance.",
                  ),
                  audit: t(
                    "A submitted command would record the idempotency key, actor, reason, attempt, result, and trace ID.",
                  ),
                }
              : reviewMode === "reconcile"
                ? {
                    objectIdentity: "NPI-ERP-RECONCILIATION",
                    version: "2026-07-21T14:20:00Z",
                    impact: t(
                      "Reconciliation compares NPI One requests with ERPNext responses. It does not overwrite either system.",
                    ),
                    permission: t(
                      "Integration operator permission is required.",
                    ),
                    irreversible: t(
                      "No formal ERPNext object is created or changed by this prototype reconciliation.",
                    ),
                    failureHandling: t(
                      "Unmatched operations remain visible with their trace IDs and recovery state.",
                    ),
                    audit: t(
                      "A submitted command would record the comparison scope, actor, timestamp, result, and trace IDs.",
                    ),
                  }
                : {
                    objectIdentity: "TL-26018-01 / TOOL-ASSET",
                    version: "v3 / ACCEPTANCE-A01",
                    impact: t(
                      "The approved tooling acceptance snapshot will be locked for a new tool asset execution request.",
                    ),
                    permission: t(
                      "Integration operator permission is required.",
                    ),
                    irreversible: t(
                      "ERPNext may create a formal object only after its own validation succeeds.",
                    ),
                    failureHandling: t(
                      "A validation or target-system failure remains visible and does not report ERPNext completion.",
                    ),
                    audit: t(
                      "A submitted command would record the idempotency key, input hash, actor, reason, result, and trace ID.",
                    ),
                  }
          }
          onCancel={() => {
            setReviewMode(null);
          }}
          onConfirm={(reason) => {
            setPreparedOperation({ mode: reviewMode, reason });
            setReviewMode(null);
          }}
          title={
            reviewMode === "retry"
              ? t("ERPNext retry impact review")
              : reviewMode === "reconcile"
                ? t("Reconciliation impact review")
                : t("New execution request impact review")
          }
        />
      ) : null}
    </article>
  );
}
