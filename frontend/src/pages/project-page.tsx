import { useCallback, useEffect, useRef, useState } from "react";

import {
  ProjectRequestCancelledError,
  type ProjectCockpitDataSource,
} from "../api/project-data-source";
import type {
  ProjectDomainWorkItemsDataSource,
  ProjectWorkContextDataSource,
} from "../api/project-work-data-source";
import type { ProjectControlsDataSource } from "../api/project-controls-data-source";
import type { DocumentDataSource } from "../api/document-data-source";
import type { EngineeringBomDataSource } from "../api/ebom-data-source";
import type { EngineeringBomPublishRequestDataSource } from "../api/publish-request-data-source";
import type { ItemPublishDataSource } from "../api/item-publish-data-source";
import type { MbomPublishDataSource } from "../api/mbom-publish-data-source";
import type { ControlledPrintDataSource } from "../api/controlled-print-data-source";
import type { ReadinessDataSource } from "../api/readiness-data-source";
import type { ProductionTransitionDataSource } from "../api/production-transition-data-source";
import type { ChangeControlDataSource } from "../api/change-control-data-source";
import type { CollaborationDataSource } from "../api/collaboration-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type {
  ReportWorkspaceDirty,
  RequestWorkspaceTransition,
} from "../app/workspace-navigation";
import {
  DockedInspector,
  MetricStrip,
  ObjectHeader,
  SectionAnchors,
} from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { ControlledPrintAction } from "../components/controlled-print-action";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
  SourceSystemIdentity,
} from "../components/primitives";
import type {
  ProjectCockpitViewModel,
  ProjectLifecycleState,
  ProjectReferenceType,
  ProjectType,
} from "../domain/view-models";
import { formatDate, formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";
import { ProjectWorkspace } from "./project-workspace";

type FailureKind =
  | "not_found"
  | "no_permission"
  | "validation"
  | "conflict"
  | "retryable"
  | "final";

type ProjectLoadState =
  | { kind: "loading"; globalId: string }
  | { kind: "loaded"; globalId: string; cockpit: ProjectCockpitViewModel }
  | {
      kind: "failed";
      globalId: string;
      failureKind: FailureKind;
      failure: RequestFailure;
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

function projectTypeLabel(
  t: ReturnType<typeof useI18n>["t"],
  projectType: ProjectType,
): string {
  switch (projectType) {
    case "customer_owned_tool":
      return t("Customer-owned tool project");
    case "new_tool":
      return t("New tool project");
    case "tool_change":
      return t("Tool change project");
  }
}

function referenceTypeLabel(
  t: ReturnType<typeof useI18n>["t"],
  type: ProjectReferenceType,
): string {
  switch (type) {
    case "customer":
      return t("Customer");
    case "product":
      return t("Product");
    case "part":
      return t("Part");
    case "tooling":
      return t("Tooling");
    case "order":
      return t("Order");
  }
}

function projectStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: ProjectLifecycleState,
): string {
  switch (state) {
    case "draft":
      return t("Draft");
    case "proposed":
      return t("Proposed");
    case "active":
      return t("Active");
    case "on_hold":
      return t("On hold");
    case "completed":
      return t("Completed");
    case "cancelled":
      return t("Cancelled");
  }
}

function ProjectLoadingSurface(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <article className="page page--object">
      <section
        aria-busy="true"
        aria-label={t("Loading project cockpit")}
        className="state-surface state-surface--loading"
        role="status"
      >
        <div className="skeleton skeleton--title" />
        <div className="skeleton" />
        <div className="skeleton" />
        <span className="visually-hidden">{t("Loading project cockpit")}</span>
      </section>
    </article>
  );
}

function ProjectFailureSurface({
  failure,
  failureKind,
  navigate,
  retry,
}: {
  failure: RequestFailure;
  failureKind: FailureKind;
  navigate: (target: string) => void;
  retry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const content = {
    not_found: {
      title: t("Project unavailable"),
      detail: t(
        "The project was not found or is not available to your account.",
      ),
    },
    no_permission: {
      title: t("Project access is not available"),
      detail: t(
        "Your account cannot open this project. No protected project data was displayed.",
      ),
    },
    validation: {
      title: t("The project address is invalid"),
      detail: t(
        "Open the project from an authorized work item or project link.",
      ),
    },
    conflict: {
      title: t("The project view is out of date"),
      detail: t("Reload the project before continuing with current data."),
    },
    retryable: {
      title: t("The project could not be loaded"),
      detail: t(
        "Retry the live project request or share the displayed reference ID with support.",
      ),
    },
    final: {
      title: t("The project response could not be used safely"),
      detail: t(
        "No project data was displayed. Share the displayed reference ID with support before trying another action.",
      ),
    },
  }[failureKind];
  const canRetry = failureKind === "retryable" || failureKind === "conflict";
  return (
    <article className="page page--object">
      <section className="state-surface" aria-labelledby="project-error-title">
        <SemanticStatus
          label={failureKind === "conflict" ? t("Conflict") : t("Error")}
          tone={failureKind === "conflict" ? "warning" : "danger"}
        />
        <h1 id="project-error-title">{content.title}</h1>
        <p>{content.detail}</p>
        <RequestFailurePanel failure={failure} />
        <div className="detail-actions">
          {canRetry ? (
            <Button icon="refresh" onClick={retry} visual="primary">
              {failureKind === "conflict" ? t("Reload project") : t("Retry")}
            </Button>
          ) : null}
          <Button
            onClick={() => {
              navigate("/work");
            }}
            visual={canRetry ? "secondary" : "primary"}
          >
            {t("Return to My Work")}
          </Button>
        </div>
      </section>
    </article>
  );
}

function ProjectCockpit({
  cockpit,
  controlsDataSource,
  controlledPrintDataSource,
  contextDataSource,
  documentDataSource,
  domainWorkItemsDataSource,
  engineeringBomDataSource,
  itemPublishDataSource,
  mbomPublishDataSource,
  publishRequestDataSource,
  productionTransitionDataSource,
  readinessDataSource,
  changeControlDataSource,
  collaborationDataSource,
  navigate,
  reportWorkspaceDirty,
  requestWorkspaceTransition,
}: {
  cockpit: ProjectCockpitViewModel;
  controlsDataSource?: ProjectControlsDataSource | undefined;
  controlledPrintDataSource?: ControlledPrintDataSource | undefined;
  contextDataSource?: ProjectWorkContextDataSource | undefined;
  documentDataSource?: DocumentDataSource | undefined;
  domainWorkItemsDataSource?: ProjectDomainWorkItemsDataSource | undefined;
  engineeringBomDataSource?: EngineeringBomDataSource | undefined;
  itemPublishDataSource?: ItemPublishDataSource | undefined;
  mbomPublishDataSource?: MbomPublishDataSource | undefined;
  publishRequestDataSource?: EngineeringBomPublishRequestDataSource | undefined;
  productionTransitionDataSource?: ProductionTransitionDataSource | undefined;
  readinessDataSource?: ReadinessDataSource | undefined;
  changeControlDataSource?: ChangeControlDataSource | undefined;
  collaborationDataSource?: CollaborationDataSource | undefined;
  navigate: (target: string) => void;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  requestWorkspaceTransition?: RequestWorkspaceTransition | undefined;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const {
    project: sourceProject,
    templateRef,
    references,
    gates,
    permissions,
  } = cockpit;
  const [projectControlState, setProjectControlState] = useState({
    state: sourceProject.state,
    version: sourceProject.version,
  });
  const synchronizeProjectControlState = useCallback(
    (changedProject: {
      globalId: string;
      state: ProjectLifecycleState;
      version: number;
    }): void => {
      if (changedProject.globalId !== sourceProject.globalId) return;
      setProjectControlState((current) =>
        changedProject.version < current.version ||
        (changedProject.version === current.version &&
          changedProject.state === current.state)
          ? current
          : {
              state: changedProject.state,
              version: changedProject.version,
            },
      );
    },
    [sourceProject.globalId],
  );
  const project = {
    ...sourceProject,
    state: projectControlState.state,
    version: projectControlState.version,
  };
  const currentCockpit = { ...cockpit, project };
  const readOnly = !permissions.canContribute;
  const empty = references.length === 0;
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
              "You have view-only access. Project commands are not available in this cockpit.",
            )}
          </span>
        </div>
      ) : null}
      {empty ? (
        <div className="scenario-banner scenario-banner--empty" role="status">
          <SemanticStatus label={t("Empty")} />
          <span>{t("This project has no governed object references.")}</span>
        </div>
      ) : null}
      <ObjectHeader
        code={project.businessCode}
        metadata={
          <span>
            {t("Project type")}: {projectTypeLabel(t, project.projectType)} ·{" "}
            {t("Owner")}:{" "}
            <span data-language-exempt="business-data">
              {project.ownerUserId}
            </span>{" "}
            · {t("Target SOP")}:{" "}
            <time dateTime={project.targetSop}>
              {formatDate(locale, project.targetSop)}
            </time>
          </span>
        }
        name={project.title}
        secondaryAction={
          controlledPrintDataSource ? (
            <ControlledPrintAction
              dataSource={controlledPrintDataSource}
              key={`${project.globalId}:${String(project.version)}:${locale}`}
              projectId={project.globalId}
              source={{
                sourceGlobalId: project.globalId,
                sourceKind: "npi.project",
                sourceVersion: project.version,
              }}
            />
          ) : undefined
        }
        source={project.source}
        status={
          <SemanticStatus
            label={projectStateLabel(t, project.state)}
            tone={
              project.state === "cancelled"
                ? "danger"
                : project.state === "completed"
                  ? "success"
                  : project.state === "on_hold"
                    ? "warning"
                    : "info"
            }
          />
        }
      />
      <ProjectWorkspace
        cockpit={currentCockpit}
        controlsDataSource={controlsDataSource}
        contextDataSource={contextDataSource}
        documentDataSource={documentDataSource}
        domainWorkItemsDataSource={domainWorkItemsDataSource}
        engineeringBomDataSource={engineeringBomDataSource}
        itemPublishDataSource={itemPublishDataSource}
        mbomPublishDataSource={mbomPublishDataSource}
        publishRequestDataSource={publishRequestDataSource}
        productionTransitionDataSource={productionTransitionDataSource}
        readinessDataSource={readinessDataSource}
        changeControlDataSource={changeControlDataSource}
        collaborationDataSource={collaborationDataSource}
        navigate={navigate}
        onProjectChanged={synchronizeProjectControlState}
        reportWorkspaceDirty={reportWorkspaceDirty}
        requestWorkspaceTransition={requestWorkspaceTransition}
        overview={
          <>
            <MetricStrip
              metrics={[
                {
                  label: t("Project version"),
                  value: formatNumber(locale, project.version, 0),
                },
                {
                  label: t("Template version"),
                  value: formatNumber(locale, templateRef.version, 0),
                },
                {
                  label: t("Gate shells"),
                  value: formatNumber(locale, gates.length, 0),
                },
                {
                  label: t("Governed references"),
                  value: formatNumber(locale, references.length, 0),
                },
              ]}
            />
            <SectionAnchors
              sections={[
                { id: "project-gates", label: t("Gate shells") },
                { id: "project-references", label: t("Governed references") },
                {
                  id: "project-context",
                  label: t("Immutable project context"),
                },
              ]}
            />
            <div className="engineering-layout engineering-layout--project">
              <Panel id="project-gates" scrollableBody title={t("Gate shells")}>
                <table className="data-table data-table--compact">
                  <thead>
                    <tr>
                      <th>{t("Sequence")}</th>
                      <th>{t("Gate")}</th>
                      <th>{t("State")}</th>
                      <th>{t("Version")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gates.length ? (
                      gates.map((gate) => (
                        <tr key={gate.globalId}>
                          <td>{formatNumber(locale, gate.sequence, 0)}</td>
                          <td>
                            <Button
                              onClick={() => {
                                navigate(
                                  `/projects/${project.globalId}/gates/${gate.globalId}`,
                                );
                              }}
                              visual="ghost"
                            >
                              <strong data-language-exempt="identifier">
                                {gate.key}
                              </strong>{" "}
                              <span data-language-exempt="business-data">
                                {gate.title}
                              </span>
                            </Button>
                          </td>
                          <td>
                            <SemanticStatus label={t("Not started")} />
                          </td>
                          <td>{formatNumber(locale, gate.version, 0)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={4}>
                          {t(
                            "No Gate shells are instantiated for this project.",
                          )}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </Panel>
              <Panel
                id="project-references"
                scrollableBody
                title={t("Governed references")}
              >
                <table className="data-table data-table--compact">
                  <thead>
                    <tr>
                      <th>{t("Reference type")}</th>
                      <th>{t("Source")}</th>
                      <th>{t("Source object ID")}</th>
                      <th>{t("Global ID")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {references.length ? (
                      references.map((reference) => (
                        <tr
                          key={`${reference.type}:${reference.sourceSystem}:${reference.sourceObjectId}`}
                        >
                          <td>{referenceTypeLabel(t, reference.type)}</td>
                          <td>
                            <SourceSystemIdentity
                              sourceSystem={reference.sourceSystem}
                            />
                          </td>
                          <td data-language-exempt="identifier">
                            {reference.sourceObjectId}
                          </td>
                          <td data-language-exempt="identifier">
                            {reference.globalId ?? "—"}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={4}>
                          {t(
                            "No governed references are attached to this project.",
                          )}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </Panel>
              <DockedInspector
                id="project-context"
                title={t("Immutable project context")}
              >
                <DefinitionList
                  rows={[
                    {
                      label: t("Global ID"),
                      value: project.globalId,
                      exempt: "identifier",
                    },
                    {
                      label: t("Project template"),
                      value: templateRef.code,
                      exempt: "identifier",
                    },
                    {
                      label: t("Template version"),
                      value: formatNumber(locale, templateRef.version, 0),
                    },
                    {
                      label: t("Template snapshot hash"),
                      value: templateRef.snapshotHash,
                      exempt: "identifier",
                    },
                    {
                      label: t("Created"),
                      value: formatDateTime(locale, project.createdAt),
                    },
                    {
                      label: t("Last updated"),
                      value: formatDateTime(locale, project.lastChangedAt),
                    },
                    {
                      label: t("Last changed by"),
                      value: project.lastChangedBy,
                      exempt: "business-data",
                    },
                    {
                      label: t("Access"),
                      value: readOnly ? t("View only") : t("Contribute"),
                    },
                  ]}
                />
              </DockedInspector>
            </div>
          </>
        }
      />
    </article>
  );
}

export default function ProjectPage({
  dataSource,
  controlsDataSource,
  controlledPrintDataSource,
  contextDataSource,
  domainWorkItemsDataSource,
  documentDataSource,
  engineeringBomDataSource,
  itemPublishDataSource,
  mbomPublishDataSource,
  publishRequestDataSource,
  productionTransitionDataSource,
  readinessDataSource,
  changeControlDataSource,
  collaborationDataSource,
  globalId,
  navigate,
  reportWorkspaceDirty,
  requestWorkspaceTransition,
}: {
  dataSource: ProjectCockpitDataSource;
  controlsDataSource?: ProjectControlsDataSource | undefined;
  controlledPrintDataSource?: ControlledPrintDataSource | undefined;
  contextDataSource?: ProjectWorkContextDataSource | undefined;
  domainWorkItemsDataSource?: ProjectDomainWorkItemsDataSource | undefined;
  documentDataSource?: DocumentDataSource | undefined;
  engineeringBomDataSource?: EngineeringBomDataSource | undefined;
  itemPublishDataSource?: ItemPublishDataSource | undefined;
  mbomPublishDataSource?: MbomPublishDataSource | undefined;
  publishRequestDataSource?: EngineeringBomPublishRequestDataSource | undefined;
  productionTransitionDataSource?: ProductionTransitionDataSource | undefined;
  readinessDataSource?: ReadinessDataSource | undefined;
  changeControlDataSource?: ChangeControlDataSource | undefined;
  collaborationDataSource?: CollaborationDataSource | undefined;
  globalId: string;
  navigate: (target: string) => void;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  requestWorkspaceTransition?: RequestWorkspaceTransition | undefined;
}): React.JSX.Element {
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  const [state, setState] = useState<ProjectLoadState>({
    globalId,
    kind: "loading",
  });
  const retry = useCallback((): void => {
    generation.current += 1;
    setState({ globalId, kind: "loading" });
    setAttempt((current) => current + 1);
  }, [globalId]);

  useEffect(() => {
    const handleRefresh = (): void => {
      retry();
    };
    globalThis.addEventListener("npi:refresh-project", handleRefresh);
    return () => {
      globalThis.removeEventListener("npi:refresh-project", handleRefresh);
    };
  }, [retry]);

  useEffect(() => {
    const controller = new AbortController();
    const requestGeneration = generation.current + 1;
    generation.current = requestGeneration;
    dataSource
      .load(globalId, controller.signal)
      .then((cockpit) => {
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration
        ) {
          return;
        }
        setState({ cockpit, globalId, kind: "loaded" });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration ||
          error instanceof ProjectRequestCancelledError
        ) {
          return;
        }
        const failure = toRequestFailure(error);
        setState({
          failure,
          failureKind: classifyFailure(failure),
          globalId,
          kind: "failed",
        });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, globalId]);

  if (state.globalId !== globalId || state.kind === "loading") {
    return <ProjectLoadingSurface />;
  }
  if (state.kind === "failed") {
    return (
      <ProjectFailureSurface
        failure={state.failure}
        failureKind={state.failureKind}
        navigate={navigate}
        retry={retry}
      />
    );
  }
  return (
    <ProjectCockpit
      cockpit={state.cockpit}
      controlsDataSource={controlsDataSource}
      controlledPrintDataSource={controlledPrintDataSource}
      contextDataSource={contextDataSource}
      documentDataSource={documentDataSource}
      domainWorkItemsDataSource={domainWorkItemsDataSource}
      engineeringBomDataSource={engineeringBomDataSource}
      itemPublishDataSource={itemPublishDataSource}
      mbomPublishDataSource={mbomPublishDataSource}
      publishRequestDataSource={publishRequestDataSource}
      productionTransitionDataSource={productionTransitionDataSource}
      readinessDataSource={readinessDataSource}
      changeControlDataSource={changeControlDataSource}
      collaborationDataSource={collaborationDataSource}
      key={`${state.cockpit.project.globalId}:${String(state.cockpit.project.version)}`}
      navigate={navigate}
      reportWorkspaceDirty={reportWorkspaceDirty}
      requestWorkspaceTransition={requestWorkspaceTransition}
    />
  );
}
