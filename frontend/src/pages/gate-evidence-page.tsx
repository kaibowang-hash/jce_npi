import { useCallback, useEffect, useRef, useState } from "react";

import {
  GateEvidenceRequestCancelledError,
  type GateEvidenceDataSource,
} from "../api/gate-evidence-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import {
  DockedInspector,
  MetricStrip,
  ObjectHeader,
  SectionAnchors,
} from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import type {
  GateEvidenceReferenceViewModel,
  GateEvidenceScanState,
  GateEvidenceViewModel,
  GateRequirementEvidenceState,
  GateRequirementViewModel,
} from "../domain/view-models";
import {
  gateEvidenceKindLabel,
  gateEvidenceScanStateLabel,
  gateRequirementClassificationLabel,
  gateRequirementEvidenceStateLabel,
} from "../i18n/copy";
import {
  formatDate,
  formatDateTime,
  formatList,
  formatNumber,
} from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";

type FailureKind =
  | "not_found"
  | "no_permission"
  | "validation"
  | "conflict"
  | "retryable"
  | "final";

type GateEvidenceLoadState =
  | { kind: "loading"; projectGlobalId: string; gateGlobalId: string }
  | {
      kind: "loaded";
      projectGlobalId: string;
      gateGlobalId: string;
      evidence: GateEvidenceViewModel;
    }
  | {
      kind: "failed";
      projectGlobalId: string;
      gateGlobalId: string;
      failureKind: FailureKind;
      failure: RequestFailure;
    };

const source = {
  sourceSystem: "NPI_ONE" as const,
  editableIn: "NPI_ONE" as const,
  syncState: "local" as const,
};

function classifyFailure(failure: RequestFailure): FailureKind {
  if (failure.kind === "request_not_ready") return "validation";
  if (failure.kind === "network") return "retryable";
  const status = failure.problem?.status;
  if (status === 404) return "not_found";
  if (status === 401 || status === 403) return "no_permission";
  if (status === 422) return "validation";
  if (status === 409) return "conflict";
  if (failure.problem?.retryable) return "retryable";
  return "final";
}

function evidenceStateTone(
  state: GateRequirementEvidenceState,
): "neutral" | "info" | "success" | "warning" | "danger" {
  switch (state) {
    case "missing":
    case "scan_failed":
    case "scan_infected":
      return "danger";
    case "scan_pending":
      return "warning";
    case "scan_clean":
      return "success";
    case "attached":
      return "info";
  }
}

function scanStateTone(
  state: GateEvidenceScanState,
): "success" | "warning" | "danger" {
  switch (state) {
    case "clean":
      return "success";
    case "pending":
      return "warning";
    case "failed":
    case "infected":
      return "danger";
  }
}

function GateEvidenceLoadingSurface(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <article className="page page--object">
      <section
        aria-busy="true"
        aria-label={t("Loading Gate evidence workspace")}
        className="state-surface state-surface--loading"
        role="status"
      >
        <div className="skeleton skeleton--title" />
        <div className="skeleton" />
        <div className="skeleton" />
        <span className="visually-hidden">
          {t("Loading Gate evidence workspace")}
        </span>
      </section>
    </article>
  );
}

function GateEvidenceFailureSurface({
  failure,
  failureKind,
  navigate,
  projectGlobalId,
  retry,
}: {
  failure: RequestFailure;
  failureKind: FailureKind;
  navigate: (target: string) => void;
  projectGlobalId: string;
  retry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const content = {
    not_found: {
      title: t("Gate evidence is unavailable"),
      detail: t(
        "The Gate evidence workspace was not found or is not available to your account.",
      ),
    },
    no_permission: {
      title: t("Gate evidence access is not available"),
      detail: t(
        "Your account cannot open this Gate evidence workspace. No protected evidence data was displayed.",
      ),
    },
    validation: {
      title: t("The Gate evidence address is invalid"),
      detail: t(
        "Open Gate evidence from an authorized Project Gate reference.",
      ),
    },
    conflict: {
      title: t("The Gate evidence view is out of date"),
      detail: t("Reload Gate evidence before continuing with current data."),
    },
    retryable: {
      title: t("Gate evidence could not be loaded"),
      detail: t(
        "Retry the live Gate evidence request or share the displayed reference ID with support.",
      ),
    },
    final: {
      title: t("The Gate evidence response could not be used safely"),
      detail: t(
        "No Gate evidence was displayed. Share the displayed reference ID with support before trying another action.",
      ),
    },
  }[failureKind];
  const canRetry = failureKind === "retryable" || failureKind === "conflict";
  return (
    <article className="page page--object">
      <section
        aria-labelledby="gate-evidence-error-title"
        className="state-surface"
      >
        <SemanticStatus
          label={failureKind === "conflict" ? t("Conflict") : t("Error")}
          tone={failureKind === "conflict" ? "warning" : "danger"}
        />
        <h1 id="gate-evidence-error-title">{content.title}</h1>
        <p>{content.detail}</p>
        <RequestFailurePanel failure={failure} />
        <div className="detail-actions">
          {canRetry ? (
            <Button icon="refresh" onClick={retry} visual="primary">
              {failureKind === "conflict"
                ? t("Reload Gate evidence")
                : t("Retry")}
            </Button>
          ) : null}
          <Button
            onClick={() => {
              navigate(
                failureKind === "validation"
                  ? "/work"
                  : `/projects/${projectGlobalId}`,
              );
            }}
            visual={canRetry ? "secondary" : "primary"}
          >
            {failureKind === "validation"
              ? t("Return to My Work")
              : t("Return to project")}
          </Button>
        </div>
      </section>
    </article>
  );
}

function RequirementTable({
  requirements,
  selectedRequirement,
  selectRequirement,
}: {
  requirements: readonly GateRequirementViewModel[];
  selectedRequirement: GateRequirementViewModel;
  selectRequirement: (requirement: GateRequirementViewModel) => void;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <table
      aria-label={t("Gate requirements")}
      className="data-table data-table--compact gate-requirements-table"
    >
      <thead>
        <tr>
          <th>{t("Requirement")}</th>
          <th>{t("Classification")}</th>
          <th>{t("Evidence state")}</th>
        </tr>
      </thead>
      <tbody>
        {requirements.map((requirement) => (
          <tr
            aria-selected={requirement.key === selectedRequirement.key}
            key={requirement.key}
          >
            <td>
              <button
                className="table-selection-button"
                onClick={() => {
                  selectRequirement(requirement);
                }}
                type="button"
              >
                <strong data-language-exempt="identifier">
                  {requirement.key}
                </strong>
                <span data-language-exempt="business-data">
                  {requirement.title}
                </span>
              </button>
            </td>
            <td>
              {gateRequirementClassificationLabel(
                t,
                requirement.classification,
              )}{" "}
              <span data-language-exempt="identifier">
                {requirement.priority}
              </span>
            </td>
            <td>
              <SemanticStatus
                label={gateRequirementEvidenceStateLabel(
                  t,
                  requirement.evidenceState,
                )}
                tone={evidenceStateTone(requirement.evidenceState)}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function EvidenceTable({
  evidence,
  selectedEvidence,
  selectEvidence,
}: {
  evidence: readonly GateEvidenceReferenceViewModel[];
  selectedEvidence: GateEvidenceReferenceViewModel | null;
  selectEvidence: (evidence: GateEvidenceReferenceViewModel) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  return (
    <table
      aria-label={t("Controlled evidence")}
      className="data-table data-table--compact gate-evidence-table"
    >
      <thead>
        <tr>
          <th>{t("Evidence")}</th>
          <th>{t("Revision")}</th>
          <th>{t("Scan State")}</th>
        </tr>
      </thead>
      <tbody>
        {evidence.length ? (
          evidence.map((reference) => (
            <tr
              aria-selected={reference.globalId === selectedEvidence?.globalId}
              key={reference.globalId}
            >
              <td>
                <button
                  className="table-selection-button"
                  onClick={() => {
                    selectEvidence(reference);
                  }}
                  type="button"
                >
                  {gateEvidenceKindLabel(t, reference.kind)}
                  <span data-language-exempt="identifier">
                    {reference.sourceGlobalId}
                  </span>
                </button>
              </td>
              <td>{formatNumber(locale, reference.revision, 0)}</td>
              <td>
                {reference.file ? (
                  <SemanticStatus
                    label={gateEvidenceScanStateLabel(
                      t,
                      reference.file.scanState,
                    )}
                    tone={scanStateTone(reference.file.scanState)}
                  />
                ) : (
                  t("Not applicable")
                )}
              </td>
            </tr>
          ))
        ) : (
          <tr>
            <td colSpan={3}>{t("No controlled evidence is attached.")}</td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function GateEvidenceWorkspace({
  view,
}: {
  view: GateEvidenceViewModel;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const { project, gate, requirements, summary, permissions } = view;
  const [selectedRequirementKey, setSelectedRequirementKey] = useState(
    requirements[0]?.key ?? "",
  );
  const selectedRequirementCandidate =
    requirements.find(
      (requirement) => requirement.key === selectedRequirementKey,
    ) ?? requirements[0];
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(
    selectedRequirementCandidate?.evidence[0]?.globalId ?? "",
  );
  if (!selectedRequirementCandidate) {
    throw new Error("A validated Gate evidence response has no requirements.");
  }
  const selectedRequirement = selectedRequirementCandidate;
  const selectedEvidence =
    selectedRequirement.evidence.find(
      (evidence) => evidence.globalId === selectedEvidenceId,
    ) ??
    selectedRequirement.evidence[0] ??
    null;
  const readOnly = !permissions.canAttachEvidence;
  const selectRequirement = (requirement: GateRequirementViewModel): void => {
    setSelectedRequirementKey(requirement.key);
    setSelectedEvidenceId(requirement.evidence[0]?.globalId ?? "");
  };
  const overallStatus =
    summary.missingRequiredCount > 0
      ? {
          label: t("Required evidence is missing"),
          tone: "danger" as const,
        }
      : summary.unsafeScanCount > 0
        ? {
            label: t("Evidence scan requires attention"),
            tone: "warning" as const,
          }
        : {
            label: t("Exact evidence references recorded"),
            tone: "success" as const,
          };
  return (
    <article className="page page--object">
      {readOnly ? (
        <div
          className="scenario-banner scenario-banner--read_only"
          role="status"
        >
          <SemanticStatus label={t("Read only")} tone="info" />
          <span>
            {t(
              "You have view-only access. Evidence attachment is not available in this workspace.",
            )}
          </span>
        </div>
      ) : null}
      {summary.evidenceCount === 0 ? (
        <div className="scenario-banner scenario-banner--empty" role="status">
          <SemanticStatus label={t("No evidence")} />
          <span>
            {t(
              "This Gate has frozen requirements but no controlled evidence references.",
            )}
          </span>
        </div>
      ) : null}
      {summary.unsafeScanCount > 0 ? (
        <div className="scenario-banner scenario-banner--partial" role="status">
          <SemanticStatus
            label={t("Unsafe scan state remains visible")}
            tone="danger"
          />
          <span>
            {t(
              "Pending, failed, or infected file scans are not represented as clean evidence.",
            )}
          </span>
        </div>
      ) : null}
      <ObjectHeader
        code={`${gate.key} / ${project.businessCode}`}
        metadata={
          <span>
            {t("Project")}:{" "}
            <span data-language-exempt="business-data">{project.title}</span> ·{" "}
            {t("Due date")}:{" "}
            <time dateTime={gate.dueDate}>
              {formatDate(locale, gate.dueDate)}
            </time>{" "}
            · {t("Gate version")}: {formatNumber(locale, gate.version, 0)} ·{" "}
            {t("Template version")}:{" "}
            {formatNumber(locale, gate.templateRef.version, 0)}
          </span>
        }
        name={gate.title}
        source={source}
        status={
          <SemanticStatus
            label={overallStatus.label}
            tone={overallStatus.tone}
          />
        }
      />
      <MetricStrip
        metrics={[
          {
            label: t("Required requirements"),
            value: formatNumber(locale, summary.requiredCount, 0),
          },
          {
            label: t("Missing required evidence"),
            value: formatNumber(locale, summary.missingRequiredCount, 0),
            tone: summary.missingRequiredCount > 0 ? "danger" : "neutral",
          },
          {
            label: t("Unsafe scan results"),
            value: formatNumber(locale, summary.unsafeScanCount, 0),
            tone: summary.unsafeScanCount > 0 ? "danger" : "neutral",
          },
          {
            label: t("Evidence references"),
            value: formatNumber(locale, summary.evidenceCount, 0),
          },
        ]}
      />
      <SectionAnchors
        sections={[
          { id: "gate-requirements", label: t("Gate requirements") },
          { id: "gate-controlled-evidence", label: t("Controlled evidence") },
          { id: "gate-frozen-context", label: t("Frozen Gate context") },
        ]}
      />
      <div className="review-layout gate-evidence-layout">
        <Panel
          id="gate-requirements"
          scrollableBody
          title={t("Gate requirements")}
        >
          <RequirementTable
            requirements={requirements}
            selectedRequirement={selectedRequirement}
            selectRequirement={selectRequirement}
          />
        </Panel>
        <Panel
          id="gate-controlled-evidence"
          scrollableBody
          title={t("Controlled evidence")}
        >
          <EvidenceTable
            evidence={selectedRequirement.evidence}
            selectedEvidence={selectedEvidence}
            selectEvidence={(evidence) => {
              setSelectedEvidenceId(evidence.globalId);
            }}
          />
          {selectedEvidence ? (
            <div className="gate-evidence-detail">
              <DefinitionList
                rows={[
                  {
                    label: t("Evidence kind"),
                    value: gateEvidenceKindLabel(t, selectedEvidence.kind),
                  },
                  {
                    label: t("Source object type"),
                    value: gateEvidenceKindLabel(
                      t,
                      selectedEvidence.sourceObjectType,
                    ),
                  },
                  {
                    label: t("Source global ID"),
                    value: selectedEvidence.sourceGlobalId,
                    exempt: "identifier",
                  },
                  {
                    label: t("Exact revision"),
                    value: formatNumber(locale, selectedEvidence.revision, 0),
                  },
                  {
                    label: t("Object hash"),
                    value: selectedEvidence.objectHash,
                    exempt: "identifier",
                  },
                  {
                    label: t("Recorded"),
                    value: formatDateTime(locale, selectedEvidence.createdAt),
                  },
                  {
                    label: t("Recorded by"),
                    value: selectedEvidence.createdBy,
                    exempt: "business-data",
                  },
                  ...(selectedEvidence.file
                    ? [
                        {
                          label: t("File name"),
                          value: selectedEvidence.file.fileName,
                          exempt: "business-data" as const,
                        },
                        {
                          label: t("File media type"),
                          value: selectedEvidence.file.mimeType,
                          exempt: "identifier" as const,
                        },
                        {
                          label: t("File size"),
                          value: (
                            <>
                              {formatNumber(
                                locale,
                                selectedEvidence.file.sizeBytes,
                                0,
                              )}{" "}
                              <span data-language-exempt="unit">B</span>
                            </>
                          ),
                        },
                        {
                          label: t("Scan State"),
                          value: gateEvidenceScanStateLabel(
                            t,
                            selectedEvidence.file.scanState,
                          ),
                        },
                      ]
                    : []),
                ]}
              />
            </div>
          ) : (
            <p className="context-help">
              {t(
                "Select a requirement with evidence to inspect its exact controlled reference.",
              )}
            </p>
          )}
        </Panel>
        <DockedInspector
          id="gate-frozen-context"
          title={t("Frozen Gate context")}
        >
          <DefinitionList
            rows={[
              {
                label: t("Requirement key"),
                value: selectedRequirement.key,
                exempt: "identifier",
              },
              {
                label: t("Requirement title"),
                value: selectedRequirement.title,
                exempt: "business-data",
              },
              {
                label: t("Classification"),
                value: gateRequirementClassificationLabel(
                  t,
                  selectedRequirement.classification,
                ),
              },
              {
                label: t("Priority"),
                value: selectedRequirement.priority,
                exempt: "identifier",
              },
              {
                label: t("Owner"),
                value: (
                  <span data-language-exempt="business-data">
                    {selectedRequirement.owner.displayName} ·{" "}
                    {selectedRequirement.owner.userId}
                  </span>
                ),
              },
              {
                label: t("Reviewers"),
                value: (
                  <ul className="compact-value-list">
                    {selectedRequirement.reviewers.map((reviewer) => (
                      <li
                        data-language-exempt="business-data"
                        key={reviewer.memberId}
                      >
                        {reviewer.displayName} · {reviewer.userId}
                      </li>
                    ))}
                  </ul>
                ),
              },
              {
                label: t("Due date"),
                value: formatDate(locale, selectedRequirement.dueDate),
              },
              {
                label: t("Allowed evidence kinds"),
                value: formatList(
                  locale,
                  selectedRequirement.allowedEvidenceKinds.map((kind) =>
                    gateEvidenceKindLabel(t, kind),
                  ),
                ),
              },
              {
                label: t("Evidence count"),
                value: formatNumber(
                  locale,
                  selectedRequirement.evidence.length,
                  0,
                ),
              },
              {
                label: t("Gate template global ID"),
                value: gate.templateRef.globalId,
                exempt: "identifier",
              },
              {
                label: t("Gate template version"),
                value: formatNumber(locale, gate.templateRef.version, 0),
              },
              {
                label: t("Gate template snapshot hash"),
                value: gate.templateRef.snapshotHash,
                exempt: "identifier",
              },
              {
                label: t("Requirement snapshot hash"),
                value: gate.requirementSnapshotHash,
                exempt: "identifier",
              },
              {
                label: t("Frozen"),
                value: formatDateTime(locale, gate.frozenAt),
              },
              {
                label: t("Frozen by"),
                value: gate.frozenBy,
                exempt: "business-data",
              },
            ]}
          />
          <p className="context-help">
            {t(
              "Requirement evidence completeness does not mean this Gate is ready for a decision.",
            )}
          </p>
        </DockedInspector>
      </div>
    </article>
  );
}

export default function GateEvidencePage({
  dataSource,
  gateGlobalId,
  navigate,
  projectGlobalId,
}: {
  dataSource: GateEvidenceDataSource;
  gateGlobalId: string;
  navigate: (target: string) => void;
  projectGlobalId: string;
}): React.JSX.Element {
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  const [state, setState] = useState<GateEvidenceLoadState>({
    gateGlobalId,
    kind: "loading",
    projectGlobalId,
  });
  const retry = useCallback((): void => {
    generation.current += 1;
    setState({ gateGlobalId, kind: "loading", projectGlobalId });
    setAttempt((current) => current + 1);
  }, [gateGlobalId, projectGlobalId]);

  useEffect(() => {
    const handleRefresh = (): void => {
      retry();
    };
    globalThis.addEventListener("npi:refresh-gate-evidence", handleRefresh);
    return () => {
      globalThis.removeEventListener(
        "npi:refresh-gate-evidence",
        handleRefresh,
      );
    };
  }, [retry]);

  useEffect(() => {
    const controller = new AbortController();
    const requestGeneration = generation.current + 1;
    generation.current = requestGeneration;
    dataSource
      .load(projectGlobalId, gateGlobalId, controller.signal)
      .then((evidence) => {
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration
        ) {
          return;
        }
        setState({
          evidence,
          gateGlobalId,
          kind: "loaded",
          projectGlobalId,
        });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration ||
          error instanceof GateEvidenceRequestCancelledError
        ) {
          return;
        }
        const failure = toRequestFailure(error);
        setState({
          failure,
          failureKind: classifyFailure(failure),
          gateGlobalId,
          kind: "failed",
          projectGlobalId,
        });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, gateGlobalId, projectGlobalId]);

  if (
    state.projectGlobalId !== projectGlobalId ||
    state.gateGlobalId !== gateGlobalId ||
    state.kind === "loading"
  ) {
    return <GateEvidenceLoadingSurface />;
  }
  if (state.kind === "failed") {
    return (
      <GateEvidenceFailureSurface
        failure={state.failure}
        failureKind={state.failureKind}
        navigate={navigate}
        projectGlobalId={projectGlobalId}
        retry={retry}
      />
    );
  }
  return (
    <GateEvidenceWorkspace
      key={`${state.evidence.gate.globalId}:${String(state.evidence.gate.version)}`}
      view={state.evidence}
    />
  );
}
