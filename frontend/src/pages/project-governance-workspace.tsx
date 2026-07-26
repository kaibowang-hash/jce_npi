import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import type {
  AddProjectCommentCommand,
  AssessProjectHealthCommand,
  BindProjectControlPolicyCommand,
  CreateProjectLearningCommand,
  ProjectCommandContext,
  ProjectControlsDataSource,
  ProjectHealthMeasurementInput,
  ProjectLearningQuery,
} from "../api/project-controls-data-source";
import {
  mergeProjectActivityPages,
  ProjectControlsRequestCancelledError,
} from "../api/project-controls-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { DockedInspector } from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import type {
  ProjectActivityItemViewModel,
  ProjectActivityPageViewModel,
  ProjectControlAction,
  ProjectControlsViewModel,
  ProjectHealthDimension,
  ProjectHealthDimensionResultViewModel,
  ProjectHealthStatus,
  ProjectLearningKind,
  ProjectLearningPageViewModel,
  ProjectLearningViewModel,
  ProjectLifecyclePrerequisiteStatus,
  ProjectLifecycleState,
  ProjectObjectLinkType,
  ProjectObjectTargetViewModel,
  SemanticTone,
} from "../domain/view-models";
import {
  formatDateTime,
  formatDecimal,
  formatList,
  formatNumber,
} from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, focusControl, Select, TextInput } from "../ui-adapters/npi-ui";

export type ProjectGovernanceSection = "controls" | "activity" | "learning";

type ResourceState<T> =
  | { kind: "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };

type CommandState =
  | { kind: "idle" }
  | { kind: "processing" }
  | { kind: "succeeded"; message: string }
  | { kind: "failed"; failure: RequestFailure };

type ActivityContinuationState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "failed"; failure: RequestFailure };

interface RetryableOperation {
  key: string;
  execute: (context: ProjectCommandContext) => Promise<void>;
}

function healthStatusLabel(
  t: ReturnType<typeof useI18n>["t"],
  status: ProjectHealthStatus,
): string {
  switch (status) {
    case "unassessed":
      return t("Unassessed");
    case "unavailable":
      return t("Unavailable");
    case "green":
      return t("Green");
    case "yellow":
      return t("Yellow");
    case "red":
      return t("Red");
  }
}

function healthTone(status: ProjectHealthStatus): SemanticTone {
  switch (status) {
    case "green":
      return "success";
    case "yellow":
      return "warning";
    case "red":
      return "danger";
    case "unavailable":
      return "warning";
    case "unassessed":
      return "neutral";
  }
}

function healthDimensionLabel(
  t: ReturnType<typeof useI18n>["t"],
  dimension: ProjectHealthDimension,
): string {
  switch (dimension) {
    case "progress":
      return t("Progress");
    case "cost":
      return t("Cost");
    case "quality":
      return t("Quality");
    case "risk":
      return t("Risk");
  }
}

function healthRuleLabel(
  t: ReturnType<typeof useI18n>["t"],
  rule: ProjectHealthDimensionResultViewModel["ruleMode"],
): string {
  switch (rule) {
    case "manual":
      return t("Manual status");
    case "higher_is_better":
      return t("Higher is better");
    case "lower_is_better":
      return t("Lower is better");
    case "unavailable":
      return t("Source unavailable");
  }
}

function lifecycleStateLabel(
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

function lifecycleActionLabel(
  t: ReturnType<typeof useI18n>["t"],
  action: ProjectControlAction,
): string {
  switch (action) {
    case "pause":
      return t("Pause project");
    case "cancel":
      return t("Cancel project");
    case "resume":
      return t("Resume project");
    case "complete":
      return t("Complete project");
  }
}

function lifecycleReasonLabel(
  t: ReturnType<typeof useI18n>["t"],
  reason: ProjectControlsViewModel["lifecycleActions"][number]["reasonCode"],
): string {
  switch (reason) {
    case "available":
      return t("Available");
    case "policy_missing":
      return t("A bound published policy is required.");
    case "project_terminal":
      return t("The project is already terminal.");
    case "transition_not_defined":
      return t("The bound policy does not define this transition.");
    case "command_access_required":
      return t("You do not have permission to perform this action.");
    case "authority_required":
      return t("The exact frozen authority is required.");
    case "prerequisite_unavailable":
      return t("A required readiness source is unavailable.");
    case "prerequisite_blocked":
      return t("A required prerequisite is blocked.");
  }
}

function prerequisiteLabel(
  t: ReturnType<typeof useI18n>["t"],
  key: ProjectControlsViewModel["lifecycleActions"][number]["prerequisites"][number]["key"],
): string {
  switch (key) {
    case "open_blockers":
      return t("Open blockers");
    case "controlled_files":
      return t("Controlled files");
    case "handover":
      return t("Handover readiness");
    case "cost":
      return t("Cost readiness");
  }
}

function prerequisiteStatusLabel(
  t: ReturnType<typeof useI18n>["t"],
  status: ProjectLifecyclePrerequisiteStatus,
): string {
  switch (status) {
    case "satisfied":
      return t("Satisfied");
    case "blocked":
      return t("Blocked");
    case "unavailable":
      return t("Unavailable");
  }
}

function learningKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: ProjectLearningKind,
): string {
  switch (kind) {
    case "retrospective":
      return t("Retrospective");
    case "lesson":
      return t("Lesson learned");
    case "template_improvement":
      return t("Template improvement");
  }
}

function activityTypeLabel(
  t: ReturnType<typeof useI18n>["t"],
  item: ProjectActivityItemViewModel,
): string {
  switch (item.eventType) {
    case "comment_added":
      return t("Comment added");
    case "followed":
      return t("Project followed");
    case "unfollowed":
      return t("Project unfollowed");
    case "health_assessed":
      return t("Project health assessed");
    case "lifecycle_transition":
      return t("Project lifecycle changed");
    case "learning_created":
      return t("Learning record created");
  }
}

function objectLinkTypeLabel(
  t: ReturnType<typeof useI18n>["t"],
  type: ProjectObjectLinkType,
): string {
  switch (type) {
    case "project":
      return t("Project");
    case "gate":
      return t("Gate");
    case "domain_work_item":
      return t("Work item");
    case "file_revision":
      return t("File revision");
    case "learning":
      return t("Learning record");
  }
}

function typedTargetPath(target: ProjectObjectTargetViewModel): string {
  const projectId = encodeURIComponent(target.projectId);
  switch (target.kind) {
    case "project":
      return `/projects/${projectId}`;
    case "gate":
      return `/projects/${projectId}/gates/${encodeURIComponent(target.gateId)}`;
    case "project_work_item":
      return `/projects/${projectId}?tab=work-items&workItem=${encodeURIComponent(target.workItemId)}`;
    case "project_learning":
      return `/projects/${projectId}?tab=learning&learning=${encodeURIComponent(target.learningId)}`;
  }
}

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    failure.problem?.retryable === true ||
    failure.problem?.status === 409
  );
}

function canRetrySameCommand(failure: RequestFailure): boolean {
  return failure.problem?.status !== 409 && canRetry(failure);
}

function resourceFailureTitle(
  t: ReturnType<typeof useI18n>["t"],
  failure: RequestFailure,
): string {
  if (failure.problem?.status === 401 || failure.problem?.status === 403) {
    return t("Project collaboration access is not available");
  }
  if (failure.problem?.status === 409) {
    return t("The project collaboration view is out of date");
  }
  if (failure.kind === "invalid_response" || failure.kind === "unexpected") {
    return t("The project collaboration response could not be used safely");
  }
  return t("Project collaboration data is unavailable");
}

function ResourceFailure({
  failure,
  retry,
}: {
  failure: RequestFailure;
  retry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const denied =
    failure.problem?.status === 401 || failure.problem?.status === 403;
  const conflict = failure.problem?.status === 409;
  return (
    <section className="workspace-resource-state" role="alert">
      <SemanticStatus
        label={
          denied ? t("No permission") : conflict ? t("Conflict") : t("Error")
        }
        tone={conflict ? "warning" : "danger"}
      />
      <h2>{resourceFailureTitle(t, failure)}</h2>
      <p>
        {denied
          ? t("No protected collaboration data was displayed.")
          : t("Use the reference ID for support or retry when available.")}
      </p>
      <RequestFailurePanel failure={failure} />
      {canRetry(failure) ? (
        <Button icon="refresh" onClick={retry}>
          {conflict ? t("Reload latest data") : t("Retry")}
        </Button>
      ) : null}
    </section>
  );
}

function ResourceLoading({ label }: { label: string }): React.JSX.Element {
  return (
    <section
      aria-busy="true"
      aria-label={label}
      className="workspace-resource-state workspace-resource-state--loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">{label}</span>
    </section>
  );
}

function MissingDataSource(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section className="workspace-resource-state" role="status">
      <SemanticStatus label={t("Unavailable")} tone="warning" />
      <p>
        {t("The live project collaboration data source is not configured.")}
      </p>
    </section>
  );
}

function CommandFeedback({
  reload,
  retry,
  state,
}: {
  reload: () => void;
  retry: () => void;
  state: CommandState;
}): React.JSX.Element | null {
  const { t } = useI18n();
  if (state.kind === "idle") return null;
  if (state.kind === "processing") {
    return (
      <div
        aria-live="polite"
        className="governance-command-state"
        role="status"
      >
        <SemanticStatus label={t("Processing")} tone="info" />
        <span>{t("The server is validating the exact project version.")}</span>
      </div>
    );
  }
  if (state.kind === "succeeded") {
    return (
      <div
        aria-live="polite"
        className="governance-command-state"
        role="status"
      >
        <SemanticStatus label={t("Succeeded")} tone="success" />
        <span>{state.message}</span>
      </div>
    );
  }
  const conflict = state.failure.problem?.status === 409;
  return (
    <div
      className="governance-command-state governance-command-state--error"
      role="alert"
    >
      <SemanticStatus
        label={conflict ? t("Conflict") : t("Error")}
        tone={conflict ? "warning" : "danger"}
      />
      <RequestFailurePanel failure={state.failure} />
      <div className="detail-actions">
        {canRetrySameCommand(state.failure) ? (
          <Button onClick={retry}>{t("Retry same command")}</Button>
        ) : null}
        <Button icon="refresh" onClick={reload}>
          {t("Reload latest data")}
        </Button>
      </div>
    </div>
  );
}

function useCommandRunner(setState: (state: CommandState) => void): {
  cancel: () => void;
  retry: () => void;
  run: (
    execute: (context: ProjectCommandContext) => Promise<void>,
    csrfToken: string,
  ) => void;
} {
  const controllerRef = useRef<AbortController | null>(null);
  const retryRef = useRef<RetryableOperation | null>(null);
  const csrfRef = useRef("");

  const execute = useCallback(
    (operation: RetryableOperation): void => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      setState({ kind: "processing" });
      void operation
        .execute({
          csrfToken: csrfRef.current,
          idempotencyKey: operation.key,
          signal: controller.signal,
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            error instanceof ProjectControlsRequestCancelledError
          ) {
            return;
          }
          setState({ failure: toRequestFailure(error), kind: "failed" });
        });
    },
    [setState],
  );

  useEffect(
    () => () => {
      controllerRef.current?.abort();
    },
    [],
  );

  return {
    cancel: () => {
      controllerRef.current?.abort();
      retryRef.current = null;
    },
    retry: () => {
      if (retryRef.current) execute(retryRef.current);
    },
    run: (operation, csrfToken) => {
      csrfRef.current = csrfToken;
      const retryable = {
        execute: operation,
        key: globalThis.crypto.randomUUID(),
      };
      retryRef.current = retryable;
      execute(retryable);
    },
  };
}

function ControlsWorkspace({
  cockpitState,
  dataSource,
  onProjectChanged,
  projectId,
}: {
  cockpitState: ProjectLifecycleState;
  dataSource: ProjectControlsDataSource;
  onProjectChanged: (project: ProjectControlsViewModel["project"]) => void;
  projectId: string;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ResourceState<ProjectControlsViewModel>>({
    kind: "loading",
  });
  const [commandState, setCommandState] = useState<CommandState>({
    kind: "idle",
  });
  const [numericValues, setNumericValues] = useState<
    Readonly<Partial<Record<ProjectHealthDimension, string>>>
  >({});
  const [manualValues, setManualValues] = useState<
    Readonly<
      Partial<
        Record<
          ProjectHealthDimension,
          "" | Extract<ProjectHealthStatus, "green" | "yellow" | "red">
        >
      >
    >
  >({});
  const [healthReason, setHealthReason] = useState("");
  const [recoveryPlan, setRecoveryPlan] = useState("");
  const [healthValidation, setHealthValidation] = useState<string | null>(null);
  const [selectedPolicyKey, setSelectedPolicyKey] = useState("");
  const [authoritySelections, setAuthoritySelections] = useState<
    Readonly<Record<string, string>>
  >({});
  const [bindingValidation, setBindingValidation] = useState<string | null>(
    null,
  );
  const [selectedAction, setSelectedAction] =
    useState<ProjectControlAction | null>(null);
  const [reviewAction, setReviewAction] = useState<ProjectControlAction | null>(
    null,
  );
  const runner = useCommandRunner(setCommandState);

  const load = useCallback((): void => {
    runner.cancel();
    setCommandState({ kind: "idle" });
    setState({ kind: "loading" });
    setAttempt((current) => current + 1);
  }, [runner]);

  useEffect(() => {
    const controller = new AbortController();
    void dataSource
      .loadControls(projectId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setState({ kind: "loaded", value });
        onProjectChanged(value.project);
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ProjectControlsRequestCancelledError
        ) {
          return;
        }
        setState({ failure: toRequestFailure(error), kind: "failed" });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, onProjectChanged, projectId]);

  if (state.kind === "loading") {
    return <ResourceLoading label={t("Loading project controls")} />;
  }
  if (state.kind === "failed") {
    return <ResourceFailure failure={state.failure} retry={load} />;
  }
  const controls = state.value;
  const terminal =
    controls.project.state === "completed" ||
    controls.project.state === "cancelled";
  const availableAction = controls.lifecycleActions.find(
    (action) => action.action === selectedAction && action.available,
  );
  const selectedReview = controls.lifecycleActions.find(
    (action) => action.action === reviewAction && action.available,
  );
  const selectedReviewAuthority =
    selectedReview?.authoritySlot === null ||
    selectedReview?.authoritySlot === undefined
      ? undefined
      : controls.binding?.authorities.find(
          (authority) => authority.slot === selectedReview.authoritySlot,
        );
  const selectedPolicy =
    controls.bindingOptions?.policies.find(
      (policy) =>
        `${policy.policyRef.globalId}:${String(policy.policyRef.version)}` ===
        selectedPolicyKey,
    ) ?? controls.bindingOptions?.policies[0];

  const runPolicyBinding = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (
      !sessionCommandContext ||
      !controls.permissions.canBindPolicy ||
      !selectedPolicy
    ) {
      return;
    }
    const bindings = selectedPolicy.authoritySlots.map((slot) => ({
      memberGlobalId: authoritySelections[slot] ?? "",
      slot,
    }));
    if (bindings.some((binding) => !binding.memberGlobalId)) {
      setBindingValidation(
        t("Select an eligible member for every authority slot."),
      );
      return;
    }
    setBindingValidation(null);
    const command: BindProjectControlPolicyCommand = {
      bindings,
      expectedProjectVersion: controls.project.version,
      policyRef: selectedPolicy.policyRef,
    };
    runner.run(async (context) => {
      const result = await dataSource.bindPolicy(
        controls.project.globalId,
        command,
        context,
      );
      setState({ kind: "loaded", value: result });
      setAuthoritySelections({});
      setCommandState({
        kind: "succeeded",
        message: t("Exact Project Control Policy binding recorded."),
      });
      onProjectChanged(result.project);
    }, sessionCommandContext.csrfToken);
  };

  const runHealthAssessment = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!sessionCommandContext || !controls.permissions.canAssessHealth) return;
    const measurements: ProjectHealthMeasurementInput[] = [];
    for (const dimension of controls.health.dimensions) {
      const numeric = numericValues[dimension.dimension]?.trim() ?? "";
      const manual = manualValues[dimension.dimension] ?? null;
      if (
        (dimension.ruleMode === "higher_is_better" ||
          dimension.ruleMode === "lower_is_better") &&
        numeric
      ) {
        measurements.push({
          dimension: dimension.dimension,
          manualStatus: null,
          numericValue: numeric,
        });
      } else if (dimension.ruleMode === "manual" && manual) {
        measurements.push({
          dimension: dimension.dimension,
          manualStatus: manual,
          numericValue: null,
        });
      }
    }
    if (measurements.length === 0) {
      setHealthValidation(
        t("Enter at least one available health measurement."),
      );
      return;
    }
    if (
      measurements.some((measurement) => measurement.manualStatus === "red") &&
      (!healthReason.trim() || !recoveryPlan.trim())
    ) {
      setHealthValidation(
        t("A red health assessment requires a reason and recovery plan."),
      );
      return;
    }
    setHealthValidation(null);
    const command: AssessProjectHealthCommand = {
      expectedProjectVersion: controls.project.version,
      measurements,
      reason: healthReason.trim() || null,
      recoveryPlan: recoveryPlan.trim() || null,
    };
    runner.run(async (context) => {
      const result = await dataSource.assessHealth(
        controls.project.globalId,
        command,
        context,
      );
      setState({ kind: "loaded", value: result });
      setCommandState({
        kind: "succeeded",
        message: t("Project health assessment recorded."),
      });
      onProjectChanged(result.project);
    }, sessionCommandContext.csrfToken);
  };

  const runTransition = (reason: string): void => {
    if (!sessionCommandContext || !selectedReview) return;
    const command = {
      action: selectedReview.action,
      expectedProjectVersion: controls.project.version,
      reason,
    } as const;
    setReviewAction(null);
    runner.run(async (context) => {
      const result = await dataSource.transition(
        controls.project.globalId,
        command,
        context,
      );
      setState({ kind: "loaded", value: result });
      setSelectedAction(null);
      setCommandState({
        kind: "succeeded",
        message: t("Project lifecycle transition recorded."),
      });
      onProjectChanged(result.project);
    }, sessionCommandContext.csrfToken);
  };

  return (
    <>
      {cockpitState !== controls.project.state ? (
        <div className="scenario-banner" role="status">
          <SemanticStatus label={t("Updated")} tone="info" />
          <span>
            {t("The controls view contains the latest server lifecycle state.")}
          </span>
        </div>
      ) : null}
      {terminal ? (
        <div className="scenario-banner" role="status">
          <SemanticStatus label={t("Terminal project")} tone="info" />
          <span>
            {t(
              "Mutable project controls are locked. Append-only comments and learning records remain available to authorized contributors.",
            )}
          </span>
        </div>
      ) : null}
      <CommandFeedback
        reload={load}
        retry={runner.retry}
        state={commandState}
      />
      <div className="project-controls-layout">
        <Panel title={t("Control policy and authority")}>
          {controls.policy && controls.binding ? (
            <>
              <DefinitionList
                rows={[
                  {
                    label: t("Policy"),
                    value: controls.policy.title,
                    exempt: "business-data",
                  },
                  {
                    label: t("Policy code"),
                    value: controls.policy.code,
                    exempt: "identifier",
                  },
                  {
                    label: t("Policy version"),
                    value: formatNumber(locale, controls.policy.version, 0),
                  },
                  {
                    label: t("Binding version"),
                    value: formatNumber(locale, controls.binding.version, 0),
                  },
                  {
                    label: t("Project version"),
                    value: formatNumber(locale, controls.project.version, 0),
                  },
                ]}
              />
              <table className="data-table data-table--compact governance-authority-table">
                <thead>
                  <tr>
                    <th>{t("Authority slot")}</th>
                    <th>{t("Assigned member")}</th>
                    <th>{t("User")}</th>
                  </tr>
                </thead>
                <tbody>
                  {controls.binding.authorities.map((authority) => (
                    <tr key={authority.slot}>
                      <td data-language-exempt="identifier">
                        {authority.slot}
                      </td>
                      <td data-language-exempt="business-data">
                        {authority.displayName}
                      </td>
                      <td data-language-exempt="business-data">
                        {authority.userId}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <div className="governance-unavailable">
              <SemanticStatus label={t("Policy unavailable")} tone="warning" />
              <p>
                {t(
                  "No published Project Control Policy is bound. Health remains unassessed and lifecycle actions remain unavailable.",
                )}
              </p>
            </div>
          )}
          {controls.bindingOptions ? (
            <section className="governance-binding">
              <h3>{t("Bind Project Control Policy")}</h3>
              {controls.bindingOptions.policies.length === 0 ? (
                <div className="governance-unavailable" role="status">
                  <SemanticStatus
                    label={t("No published policy versions")}
                    tone="warning"
                  />
                  <p>
                    {t(
                      "No enabled published Project Control Policy version is available for binding.",
                    )}
                  </p>
                </div>
              ) : controls.bindingOptions.eligibleMembers.length === 0 ? (
                <div className="governance-unavailable" role="status">
                  <SemanticStatus
                    label={t("No eligible project members")}
                    tone="warning"
                  />
                  <p>
                    {t(
                      "No current project member is eligible for the required authority slots. Ask a project administrator to review membership and authority eligibility.",
                    )}
                  </p>
                </div>
              ) : (
                <form onSubmit={runPolicyBinding}>
                  <label className="field-control">
                    <span>{t("Published policy version")}</span>
                    <Select
                      disabled={commandState.kind === "processing"}
                      onChange={(event) => {
                        setSelectedPolicyKey(event.currentTarget.value);
                        setAuthoritySelections({});
                        setBindingValidation(null);
                      }}
                      value={
                        selectedPolicy
                          ? `${selectedPolicy.policyRef.globalId}:${String(selectedPolicy.policyRef.version)}`
                          : ""
                      }
                    >
                      {controls.bindingOptions.policies.map((policy) => (
                        <option
                          data-language-exempt="business-data"
                          key={`${policy.policyRef.globalId}:${String(policy.policyRef.version)}`}
                          value={`${policy.policyRef.globalId}:${String(policy.policyRef.version)}`}
                        >
                          {policy.code} · {policy.title} ·{" "}
                          {formatNumber(locale, policy.policyRef.version, 0)}
                        </option>
                      ))}
                    </Select>
                  </label>
                  <div className="governance-binding-grid">
                    {selectedPolicy?.authoritySlots.map((slot) => (
                      <label className="field-control" key={slot}>
                        <span>
                          {t("Authority slot")}{" "}
                          <span data-language-exempt="identifier">{slot}</span>
                        </span>
                        <Select
                          disabled={commandState.kind === "processing"}
                          onChange={(event) => {
                            const memberGlobalId = event.currentTarget.value;
                            setAuthoritySelections((current) => ({
                              ...current,
                              [slot]: memberGlobalId,
                            }));
                          }}
                          required
                          value={authoritySelections[slot] ?? ""}
                        >
                          <option value="">
                            {t("Select eligible member")}
                          </option>
                          {controls.bindingOptions?.eligibleMembers.map(
                            (member) => (
                              <option
                                data-language-exempt="business-data"
                                key={member.memberGlobalId}
                                value={member.memberGlobalId}
                              >
                                {member.displayName} · {member.userId}
                              </option>
                            ),
                          )}
                        </Select>
                      </label>
                    ))}
                  </div>
                  <p className="governance-help">
                    {t(
                      "The server revalidates the exact published policy version and current eligible project members before binding.",
                    )}
                  </p>
                  {bindingValidation ? (
                    <p className="field-error" role="alert">
                      {bindingValidation}
                    </p>
                  ) : null}
                  <div className="detail-actions governance-form-actions">
                    <Button
                      disabled={
                        !sessionCommandContext ||
                        commandState.kind === "processing"
                      }
                      type="submit"
                    >
                      {controls.binding
                        ? t("Replace policy binding")
                        : t("Bind policy")}
                    </Button>
                  </div>
                </form>
              )}
            </section>
          ) : null}
        </Panel>

        <Panel
          actions={
            <SemanticStatus
              label={healthStatusLabel(t, controls.health.overallStatus)}
              tone={healthTone(controls.health.overallStatus)}
            />
          }
          title={t("Project health")}
        >
          <form onSubmit={runHealthAssessment}>
            <span
              className="visually-hidden"
              id="new-manual-health-status-label"
            >
              {t("New manual health status")}
            </span>
            <span
              className="visually-hidden"
              id="new-numeric-health-value-label"
            >
              {t("New numeric health value")}
            </span>
            <table className="data-table data-table--compact governance-health-table">
              <thead>
                <tr>
                  <th>{t("Dimension")}</th>
                  <th>{t("Rule")}</th>
                  <th>{t("Current status")}</th>
                  <th>{t("Measured value")}</th>
                </tr>
              </thead>
              <tbody>
                {controls.health.dimensions.map((dimension) => (
                  <tr key={dimension.dimension}>
                    <th
                      id={`project-health-${dimension.dimension}-dimension`}
                      scope="row"
                    >
                      {healthDimensionLabel(t, dimension.dimension)}
                    </th>
                    <td>{healthRuleLabel(t, dimension.ruleMode)}</td>
                    <td>
                      <SemanticStatus
                        label={healthStatusLabel(t, dimension.status)}
                        tone={healthTone(dimension.status)}
                      />
                    </td>
                    <td>
                      {controls.permissions.canAssessHealth &&
                      dimension.ruleMode === "manual" ? (
                        <Select
                          aria-labelledby={`new-manual-health-status-label project-health-${dimension.dimension}-dimension`}
                          disabled={commandState.kind === "processing"}
                          onChange={(event) => {
                            const manualStatus = event.currentTarget.value as
                              | ""
                              | "green"
                              | "yellow"
                              | "red";
                            setManualValues((current) => ({
                              ...current,
                              [dimension.dimension]: manualStatus,
                            }));
                          }}
                          value={manualValues[dimension.dimension] ?? ""}
                        >
                          <option value="">{t("No new measurement")}</option>
                          <option value="green">{t("Green")}</option>
                          <option value="yellow">{t("Yellow")}</option>
                          <option value="red">{t("Red")}</option>
                        </Select>
                      ) : controls.permissions.canAssessHealth &&
                        (dimension.ruleMode === "higher_is_better" ||
                          dimension.ruleMode === "lower_is_better") ? (
                        <TextInput
                          aria-labelledby={`new-numeric-health-value-label project-health-${dimension.dimension}-dimension`}
                          disabled={commandState.kind === "processing"}
                          inputMode="decimal"
                          maxLength={100}
                          onChange={(event) => {
                            const numericValue = event.currentTarget.value;
                            setNumericValues((current) => ({
                              ...current,
                              [dimension.dimension]: numericValue,
                            }));
                          }}
                          value={numericValues[dimension.dimension] ?? ""}
                        />
                      ) : dimension.numericValue !== null ? (
                        formatDecimal(locale, dimension.numericValue)
                      ) : (
                        t("Unavailable")
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {controls.permissions.canAssessHealth ? (
              <div className="governance-form-grid">
                <label className="field-control">
                  <span>{t("Assessment reason")}</span>
                  <textarea
                    disabled={commandState.kind === "processing"}
                    maxLength={2000}
                    onChange={(event) => {
                      setHealthReason(event.currentTarget.value);
                    }}
                    rows={3}
                    value={healthReason}
                  />
                </label>
                <label className="field-control">
                  <span>{t("Recovery plan")}</span>
                  <textarea
                    disabled={commandState.kind === "processing"}
                    maxLength={4000}
                    onChange={(event) => {
                      setRecoveryPlan(event.currentTarget.value);
                    }}
                    rows={3}
                    value={recoveryPlan}
                  />
                </label>
              </div>
            ) : null}
            {healthValidation ? (
              <p className="field-error" role="alert">
                {healthValidation}
              </p>
            ) : null}
            {controls.permissions.canAssessHealth ? (
              <div className="detail-actions governance-form-actions">
                <Button
                  disabled={
                    !sessionCommandContext || commandState.kind === "processing"
                  }
                  type="submit"
                >
                  {t("Assess project health")}
                </Button>
              </div>
            ) : (
              <p className="governance-help">
                {controls.policy
                  ? t(
                      "Only the exact frozen health authority can assess health.",
                    )
                  : t(
                      "Health assessment is unavailable until a policy is bound.",
                    )}
              </p>
            )}
          </form>
          {controls.health.assessment ? (
            <DefinitionList
              rows={[
                {
                  label: t("Assessed at"),
                  value: formatDateTime(
                    locale,
                    controls.health.assessment.assessedAt,
                  ),
                },
                {
                  label: t("Assessed by"),
                  value: controls.health.assessment.actor.displayName,
                  exempt: "business-data",
                },
                {
                  label: t("Reason"),
                  value: controls.health.assessment.reason ?? t("Not provided"),
                  ...(controls.health.assessment.reason
                    ? { exempt: "business-data" as const }
                    : {}),
                },
                {
                  label: t("Recovery plan"),
                  value:
                    controls.health.assessment.recoveryPlan ??
                    t("Not provided"),
                  ...(controls.health.assessment.recoveryPlan
                    ? { exempt: "business-data" as const }
                    : {}),
                },
              ]}
            />
          ) : (
            <p className="governance-help">
              {t("No immutable health assessment has been recorded.")}
            </p>
          )}
        </Panel>

        <Panel title={t("Lifecycle actions")}>
          <table className="data-table data-table--compact governance-lifecycle-table">
            <thead>
              <tr>
                <th>{t("Select")}</th>
                <th>{t("Action")}</th>
                <th>{t("Target state")}</th>
                <th>{t("Availability")}</th>
                <th>{t("Prerequisites")}</th>
              </tr>
            </thead>
            <tbody>
              {controls.lifecycleActions.map((action) => (
                <tr key={action.action}>
                  <td>
                    <input
                      aria-label={lifecycleActionLabel(t, action.action)}
                      checked={selectedAction === action.action}
                      disabled={!action.available}
                      name="project-lifecycle-action"
                      onChange={() => {
                        setSelectedAction(action.action);
                      }}
                      type="radio"
                    />
                  </td>
                  <td>{lifecycleActionLabel(t, action.action)}</td>
                  <td>{lifecycleStateLabel(t, action.targetState)}</td>
                  <td>
                    <SemanticStatus
                      label={lifecycleReasonLabel(t, action.reasonCode)}
                      tone={action.available ? "success" : "neutral"}
                    />
                    {action.authoritySlot ? (
                      <small data-language-exempt="identifier">
                        {action.authoritySlot}
                      </small>
                    ) : null}
                  </td>
                  <td>
                    {action.prerequisites.length ? (
                      <ul className="compact-value-list">
                        {action.prerequisites.map((prerequisite) => (
                          <li key={prerequisite.key}>
                            {prerequisiteLabel(t, prerequisite.key)}:{" "}
                            {prerequisiteStatusLabel(t, prerequisite.status)}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      t("None")
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="detail-actions governance-form-actions">
            <Button
              disabled={
                !availableAction ||
                !sessionCommandContext ||
                commandState.kind === "processing"
              }
              onClick={() => {
                if (availableAction) setReviewAction(availableAction.action);
              }}
              visual="primary"
            >
              {t("Review lifecycle action")}
            </Button>
          </div>
        </Panel>
      </div>
      {selectedReview ? (
        <ImpactReview
          confirmLabel={t("Execute lifecycle action")}
          contextRows={[
            {
              label: t("Project title"),
              value: controls.project.title,
              exempt: "business-data",
            },
            {
              label: t("Current state"),
              value: lifecycleStateLabel(t, controls.project.state),
            },
            {
              label: t("Target state"),
              value: lifecycleStateLabel(t, selectedReview.targetState),
            },
            {
              label: t("Policy version"),
              value: controls.policy
                ? `${controls.policy.code} / ${formatNumber(locale, controls.policy.version, 0)} / ${controls.policy.snapshotHash}`
                : t("Unavailable"),
              ...(controls.policy ? { exempt: "identifier" as const } : {}),
            },
            {
              label: t("Binding version"),
              value: controls.binding
                ? formatNumber(locale, controls.binding.version, 0)
                : t("Unavailable"),
              ...(controls.binding ? { exempt: "identifier" as const } : {}),
            },
            {
              label: t("Authority slot"),
              value: selectedReview.authoritySlot ?? t("Unavailable"),
              ...(selectedReview.authoritySlot
                ? { exempt: "identifier" as const }
                : {}),
            },
            {
              label: t("Assigned member"),
              value: selectedReviewAuthority?.displayName ?? t("Unavailable"),
              ...(selectedReviewAuthority
                ? { exempt: "business-data" as const }
                : {}),
            },
            {
              label: t("User"),
              value: selectedReviewAuthority?.userId ?? t("Unavailable"),
              ...(selectedReviewAuthority
                ? { exempt: "business-data" as const }
                : {}),
            },
            {
              label: t("Member global identifier"),
              value:
                selectedReviewAuthority?.memberGlobalId ?? t("Unavailable"),
              ...(selectedReviewAuthority
                ? { exempt: "identifier" as const }
                : {}),
            },
            {
              label: t("Prerequisites"),
              value: selectedReview.prerequisites.length ? (
                <ul className="compact-value-list">
                  {selectedReview.prerequisites.map((prerequisite) => (
                    <li key={prerequisite.key}>
                      {prerequisiteLabel(t, prerequisite.key)}:{" "}
                      {prerequisiteStatusLabel(t, prerequisite.status)}
                    </li>
                  ))}
                </ul>
              ) : (
                t("None")
              ),
            },
          ]}
          details={{
            audit: t(
              "The server records the actor, exact policy, binding, prerequisites, reason, project version, request ID, and trace ID.",
            ),
            failureHandling: t(
              "A failed command changes no displayed state. Reload current server data before choosing another action.",
            ),
            impact: lifecycleActionLabel(t, selectedReview.action),
            irreversible: t(
              "The transition is auditable. Any later state change requires another policy-authorized server action.",
            ),
            objectIdentity: controls.project.businessCode,
            permission: t(
              "The exact frozen authority assigned by the bound policy is required.",
            ),
            version: formatNumber(locale, controls.project.version, 0),
          }}
          onCancel={() => {
            setReviewAction(null);
          }}
          onConfirm={runTransition}
          reasonMaxLength={2000}
          title={t("Review project lifecycle transition")}
        />
      ) : null}
    </>
  );
}

function toggleSelection(
  values: readonly string[],
  value: string,
  selected: boolean,
): readonly string[] {
  return selected
    ? values.includes(value)
      ? values
      : [...values, value]
    : values.filter((candidate) => candidate !== value);
}

function ActivityInspector({
  item,
  navigate,
  projectId,
}: {
  item: ProjectActivityItemViewModel | undefined;
  navigate: (target: string) => void;
  projectId: string;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  if (!item) {
    return (
      <DockedInspector title={t("Activity details")}>
        <p>{t("Select an activity event to inspect its immutable detail.")}</p>
      </DockedInspector>
    );
  }
  let detail: ReactNode;
  if (item.eventType === "comment_added") {
    detail = (
      <>
        <p
          className="governance-comment-body"
          data-language-exempt="business-data"
        >
          {item.detail.body}
        </p>
        <h3>{t("Mentions")}</h3>
        {item.detail.mentions.length ? (
          <ul className="compact-value-list">
            {item.detail.mentions.map((mention) => (
              <li
                data-language-exempt="business-data"
                key={mention.memberGlobalId}
              >
                {mention.displayName} · {mention.userId}
              </li>
            ))}
          </ul>
        ) : (
          <p>{t("No mentions")}</p>
        )}
        <h3>{t("Clean file revisions")}</h3>
        {item.detail.attachments.length ? (
          <table className="data-table data-table--compact">
            <thead>
              <tr>
                <th>{t("File")}</th>
                <th>{t("Version")}</th>
                <th>{t("Scan state")}</th>
              </tr>
            </thead>
            <tbody>
              {item.detail.attachments.map((attachment) => (
                <tr key={attachment.globalId}>
                  <td data-language-exempt="business-data">
                    {attachment.fileName}
                  </td>
                  <td>{formatNumber(locale, attachment.version, 0)}</td>
                  <td>
                    <SemanticStatus label={t("Clean")} tone="success" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>{t("No file revisions")}</p>
        )}
        <h3>{t("Object links")}</h3>
        {item.detail.objectLinks.length ? (
          <ul className="governance-link-list">
            {item.detail.objectLinks.map((link) => (
              <li key={`${link.type}:${link.globalId}`}>
                <Button
                  onClick={() => {
                    navigate(typedTargetPath(link.target));
                  }}
                  visual="ghost"
                >
                  {objectLinkTypeLabel(t, link.type)} ·{" "}
                  <span data-language-exempt="business-data">{link.title}</span>
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p>{t("No object links")}</p>
        )}
      </>
    );
  } else if (item.eventType === "followed" || item.eventType === "unfollowed") {
    detail = (
      <p>
        {item.detail.active
          ? t("The actor started following this project.")
          : t("The actor stopped following this project.")}
      </p>
    );
  } else if (item.eventType === "health_assessed") {
    detail = (
      <>
        <SemanticStatus
          label={healthStatusLabel(t, item.detail.assessment.overallStatus)}
          tone={healthTone(item.detail.assessment.overallStatus)}
        />
        <DefinitionList
          rows={[
            {
              label: t("Project version"),
              value: formatNumber(locale, item.detail.projectVersion, 0),
            },
            {
              label: t("Reason"),
              value: item.detail.assessment.reason ?? t("Not provided"),
              ...(item.detail.assessment.reason
                ? { exempt: "business-data" as const }
                : {}),
            },
            {
              label: t("Recovery plan"),
              value: item.detail.assessment.recoveryPlan ?? t("Not provided"),
              ...(item.detail.assessment.recoveryPlan
                ? { exempt: "business-data" as const }
                : {}),
            },
          ]}
        />
      </>
    );
  } else if (item.eventType === "lifecycle_transition") {
    detail = (
      <DefinitionList
        rows={[
          {
            label: t("Action"),
            value: lifecycleActionLabel(t, item.detail.action),
          },
          {
            label: t("From state"),
            value: lifecycleStateLabel(t, item.detail.fromState),
          },
          {
            label: t("To state"),
            value: lifecycleStateLabel(t, item.detail.toState),
          },
          {
            label: t("Reason"),
            value: item.detail.reason,
            exempt: "business-data",
          },
          {
            label: t("Approved by"),
            value: item.detail.approvedBy.displayName,
            exempt: "business-data",
          },
          {
            label: t("Project version"),
            value: formatNumber(locale, item.detail.projectVersion, 0),
          },
        ]}
      />
    );
  } else {
    detail = (
      <>
        <DefinitionList
          rows={[
            {
              label: t("Learning kind"),
              value: learningKindLabel(t, item.detail.kind),
            },
            {
              label: t("Title"),
              value: item.detail.title,
              exempt: "business-data",
            },
          ]}
        />
        <Button
          onClick={() => {
            navigate(
              typedTargetPath({
                kind: "project_learning",
                learningId: item.detail.learningGlobalId,
                projectId,
              }),
            );
          }}
        >
          {t("Open learning record")}
        </Button>
      </>
    );
  }
  return (
    <DockedInspector title={activityTypeLabel(t, item)}>
      <DefinitionList
        rows={[
          {
            label: t("Actor"),
            value: item.actorUserId,
            exempt: "business-data",
          },
          {
            label: t("Occurred at"),
            value: formatDateTime(locale, item.occurredAt),
          },
          {
            label: t("Event ID"),
            value: item.globalId,
            exempt: "identifier",
          },
        ]}
      />
      {detail}
    </DockedInspector>
  );
}

function ActivityWorkspace({
  dataSource,
  navigate,
  projectId,
  terminal,
}: {
  dataSource: ProjectControlsDataSource;
  navigate: (target: string) => void;
  projectId: string;
  terminal: boolean;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<
    ResourceState<ProjectActivityPageViewModel>
  >({
    kind: "loading",
  });
  const [selectedId, setSelectedId] = useState("");
  const [body, setBody] = useState("");
  const [selectedMentionIds, setSelectedMentionIds] = useState<
    readonly string[]
  >([]);
  const [selectedAttachmentIds, setSelectedAttachmentIds] = useState<
    readonly string[]
  >([]);
  const [selectedObjectLinkIds, setSelectedObjectLinkIds] = useState<
    readonly string[]
  >([]);
  const [validation, setValidation] = useState<string | null>(null);
  const [commandState, setCommandState] = useState<CommandState>({
    kind: "idle",
  });
  const [continuationState, setContinuationState] =
    useState<ActivityContinuationState>({ kind: "idle" });
  const continuationControllerRef = useRef<AbortController | null>(null);
  const requestedCursorsRef = useRef<Set<string>>(new Set());
  const runner = useCommandRunner(setCommandState);

  const load = useCallback((): void => {
    continuationControllerRef.current?.abort();
    continuationControllerRef.current = null;
    requestedCursorsRef.current.clear();
    runner.cancel();
    setCommandState({ kind: "idle" });
    setContinuationState({ kind: "idle" });
    setState({ kind: "loading" });
    setAttempt((current) => current + 1);
  }, [runner]);

  useEffect(() => {
    const controller = new AbortController();
    continuationControllerRef.current?.abort();
    continuationControllerRef.current = null;
    requestedCursorsRef.current.clear();
    void dataSource
      .loadActivity(projectId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setContinuationState({ kind: "idle" });
        setState({ kind: "loaded", value });
        setSelectedMentionIds([]);
        setSelectedAttachmentIds([]);
        setSelectedObjectLinkIds([]);
        setSelectedId((current) =>
          value.items.some((item) => item.globalId === current)
            ? current
            : (value.items[0]?.globalId ?? ""),
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ProjectControlsRequestCancelledError
        ) {
          return;
        }
        setState({ failure: toRequestFailure(error), kind: "failed" });
      });
    return () => {
      controller.abort();
      continuationControllerRef.current?.abort();
      continuationControllerRef.current = null;
    };
  }, [attempt, dataSource, projectId]);

  if (state.kind === "loading") {
    return <ResourceLoading label={t("Loading project activity")} />;
  }
  if (state.kind === "failed") {
    return <ResourceFailure failure={state.failure} retry={load} />;
  }
  const page = state.value;
  const { canComment, canFollow } = page.permissions;
  const selected = page.items.find((item) => item.globalId === selectedId);

  const loadMore = (): void => {
    const cursor = page.nextCursor;
    if (cursor === null || continuationState.kind === "loading") return;
    const controller = new AbortController();
    continuationControllerRef.current?.abort();
    continuationControllerRef.current = controller;
    setContinuationState({ kind: "loading" });
    void dataSource
      .loadActivity(projectId, controller.signal, 50, cursor)
      .then((continuation) => {
        if (controller.signal.aborted) return;
        const requestedCursors = requestedCursorsRef.current;
        if (
          requestedCursors.has(cursor) ||
          (continuation.nextCursor !== null &&
            (continuation.nextCursor === cursor ||
              requestedCursors.has(continuation.nextCursor)))
        ) {
          throw new Error("Project activity cursor cycle detected.");
        }
        const merged = mergeProjectActivityPages(page, continuation);
        if (merged === null) {
          throw new Error("Project activity continuation is inconsistent.");
        }
        requestedCursors.add(cursor);
        setState((current) => {
          if (current.kind !== "loaded") return current;
          const latest = mergeProjectActivityPages(current.value, continuation);
          return latest === null ? current : { kind: "loaded", value: latest };
        });
        setContinuationState({ kind: "idle" });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ProjectControlsRequestCancelledError
        ) {
          return;
        }
        setContinuationState({
          failure: toRequestFailure(error),
          kind: "failed",
        });
      })
      .finally(() => {
        if (continuationControllerRef.current === controller) {
          continuationControllerRef.current = null;
        }
      });
  };

  const toggleFollow = (): void => {
    if (!sessionCommandContext || !canFollow) return;
    const next = !page.following;
    runner.run(async (context) => {
      const result = await dataSource.changeFollowing(
        projectId,
        next,
        page.followerVersion,
        context,
      );
      setState((current) =>
        current.kind === "loaded"
          ? {
              kind: "loaded",
              value: {
                ...current.value,
                followerVersion: result.version,
                following: result.following,
              },
            }
          : current,
      );
      setCommandState({
        kind: "succeeded",
        message: result.following
          ? t("You are now following this project.")
          : t("You are no longer following this project."),
      });
    }, sessionCommandContext.csrfToken);
  };

  const submitComment = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!sessionCommandContext || !canComment) return;
    if (!body.trim()) {
      setValidation(t("Enter a comment."));
      return;
    }
    const mentions = page.commentOptions.mentions
      .filter((mention) => selectedMentionIds.includes(mention.memberGlobalId))
      .map((mention) => ({ memberGlobalId: mention.memberGlobalId }));
    const attachments = page.commentOptions.attachments
      .filter((attachment) =>
        selectedAttachmentIds.includes(attachment.globalId),
      )
      .map((attachment) => ({
        globalId: attachment.globalId,
        version: attachment.version,
      }));
    const objectLinks = page.commentOptions.objectLinks
      .filter((link) =>
        selectedObjectLinkIds.includes(`${link.type}:${link.globalId}`),
      )
      .map((link) => ({
        globalId: link.globalId,
        type: link.type,
        version: link.version,
      }));
    setValidation(null);
    const command: AddProjectCommentCommand = {
      attachments,
      body,
      mentions,
      objectLinks,
    };
    runner.run(async (context) => {
      const result = await dataSource.addComment(projectId, command, context);
      setState((current) =>
        current.kind === "loaded"
          ? {
              kind: "loaded",
              value: {
                ...current.value,
                items: [
                  result,
                  ...current.value.items.filter(
                    (item) => item.globalId !== result.globalId,
                  ),
                ],
              },
            }
          : current,
      );
      setSelectedId(result.globalId);
      setBody("");
      setSelectedMentionIds([]);
      setSelectedAttachmentIds([]);
      setSelectedObjectLinkIds([]);
      setCommandState({
        kind: "succeeded",
        message: t("Append-only project comment recorded."),
      });
    }, sessionCommandContext.csrfToken);
  };

  return (
    <>
      {terminal ? (
        <div className="scenario-banner" role="status">
          <SemanticStatus label={t("Append-only collaboration")} tone="info" />
          <span>
            {t(
              "This terminal project still accepts authorized comments without reopening mutable project history.",
            )}
          </span>
        </div>
      ) : null}
      {!canComment && !canFollow ? (
        <div className="scenario-banner" role="status">
          <SemanticStatus label={t("Read only")} tone="info" />
          <span>
            {t(
              "You can view activity but cannot add project collaboration records.",
            )}
          </span>
        </div>
      ) : null}
      <CommandFeedback
        reload={load}
        retry={runner.retry}
        state={commandState}
      />
      <div className="project-activity-layout">
        <div className="project-activity-main">
          <Panel
            actions={
              <Button
                disabled={
                  !canFollow ||
                  !sessionCommandContext ||
                  commandState.kind === "processing"
                }
                onClick={toggleFollow}
              >
                {page.following ? t("Unfollow project") : t("Follow project")}
              </Button>
            }
            title={t("Project activity")}
          >
            {page.items.length ? (
              <table
                aria-busy={continuationState.kind === "loading"}
                className="data-table data-table--compact governance-activity-table"
              >
                <thead>
                  <tr>
                    <th>{t("Event")}</th>
                    <th>{t("Actor")}</th>
                    <th>{t("Occurred at")}</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((item) => (
                    <tr
                      aria-selected={selectedId === item.globalId}
                      className={
                        selectedId === item.globalId ? "is-selected" : undefined
                      }
                      key={item.globalId}
                      onClick={() => {
                        setSelectedId(item.globalId);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedId(item.globalId);
                        }
                      }}
                      tabIndex={0}
                    >
                      <td>{activityTypeLabel(t, item)}</td>
                      <td data-language-exempt="business-data">
                        {item.actorUserId}
                      </td>
                      <td>
                        <time dateTime={item.occurredAt}>
                          {formatDateTime(locale, item.occurredAt)}
                        </time>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="table-empty">
                {t("No project activity has been recorded.")}
              </div>
            )}
            {continuationState.kind === "failed" ? (
              <div
                className="governance-command-state governance-command-state--error"
                role="alert"
              >
                <SemanticStatus label={t("Error")} tone="danger" />
                <span>{t("More project activity could not be loaded.")}</span>
                <RequestFailurePanel
                  announce={false}
                  failure={continuationState.failure}
                />
                <div className="detail-actions">
                  <Button icon="refresh" onClick={loadMore}>
                    {t("Retry")}
                  </Button>
                </div>
              </div>
            ) : page.nextCursor !== null ? (
              <div className="detail-actions">
                <Button
                  aria-busy={continuationState.kind === "loading"}
                  disabled={continuationState.kind === "loading"}
                  onClick={loadMore}
                  visual="secondary"
                >
                  {continuationState.kind === "loading"
                    ? t("Loading more activity")
                    : t("Load more activity")}
                </Button>
              </div>
            ) : null}
          </Panel>
          {canComment ? (
            <Panel title={t("Add project comment")}>
              {page.commentOptions.truncated ? (
                <div
                  aria-live="polite"
                  className="scenario-banner scenario-banner--partial"
                  role="status"
                >
                  <SemanticStatus
                    label={t("Comment choices limited")}
                    tone="warning"
                  />
                  <span>
                    {t(
                      "Only the first 500 eligible comment choices are shown. You can still read activity and add a comment with the available choices.",
                    )}
                  </span>
                </div>
              ) : null}
              <form onSubmit={submitComment}>
                <label className="field-control">
                  <span>{t("Comment")}</span>
                  <textarea
                    disabled={commandState.kind === "processing"}
                    maxLength={4000}
                    onChange={(event) => {
                      setBody(event.currentTarget.value);
                    }}
                    required
                    rows={4}
                    value={body}
                  />
                </label>
                {page.commentOptions.mentions.length ||
                page.commentOptions.attachments.length ||
                page.commentOptions.objectLinks.length ? (
                  <div className="governance-comment-options">
                    {page.commentOptions.mentions.length ? (
                      <fieldset>
                        <legend>{t("Mention project members")}</legend>
                        <div className="governance-option-list">
                          {page.commentOptions.mentions.map((mention) => (
                            <label key={mention.memberGlobalId}>
                              <input
                                checked={selectedMentionIds.includes(
                                  mention.memberGlobalId,
                                )}
                                disabled={
                                  commandState.kind === "processing" ||
                                  (selectedMentionIds.length >= 50 &&
                                    !selectedMentionIds.includes(
                                      mention.memberGlobalId,
                                    ))
                                }
                                onChange={(event) => {
                                  const selected = event.currentTarget.checked;
                                  setSelectedMentionIds((current) =>
                                    toggleSelection(
                                      current,
                                      mention.memberGlobalId,
                                      selected,
                                    ),
                                  );
                                }}
                                type="checkbox"
                              />
                              <span data-language-exempt="business-data">
                                {mention.displayName} · {mention.userId}
                              </span>
                            </label>
                          ))}
                        </div>
                      </fieldset>
                    ) : null}
                    {page.commentOptions.attachments.length ? (
                      <fieldset>
                        <legend>{t("Attach clean file revisions")}</legend>
                        <div className="governance-option-list">
                          {page.commentOptions.attachments.map((attachment) => (
                            <label key={attachment.globalId}>
                              <input
                                checked={selectedAttachmentIds.includes(
                                  attachment.globalId,
                                )}
                                disabled={
                                  commandState.kind === "processing" ||
                                  (selectedAttachmentIds.length >= 20 &&
                                    !selectedAttachmentIds.includes(
                                      attachment.globalId,
                                    ))
                                }
                                onChange={(event) => {
                                  const selected = event.currentTarget.checked;
                                  setSelectedAttachmentIds((current) =>
                                    toggleSelection(
                                      current,
                                      attachment.globalId,
                                      selected,
                                    ),
                                  );
                                }}
                                type="checkbox"
                              />
                              <span data-language-exempt="business-data">
                                {attachment.fileName}
                              </span>
                              <span>
                                {t("Version")}{" "}
                                {formatNumber(locale, attachment.version, 0)}
                              </span>
                              <SemanticStatus
                                label={t("Clean")}
                                tone="success"
                              />
                            </label>
                          ))}
                        </div>
                      </fieldset>
                    ) : null}
                    {page.commentOptions.objectLinks.length ? (
                      <fieldset>
                        <legend>{t("Link project objects")}</legend>
                        <div className="governance-option-list">
                          {page.commentOptions.objectLinks.map((link) => {
                            const identity = `${link.type}:${link.globalId}`;
                            return (
                              <label key={identity}>
                                <input
                                  checked={selectedObjectLinkIds.includes(
                                    identity,
                                  )}
                                  disabled={
                                    commandState.kind === "processing" ||
                                    (selectedObjectLinkIds.length >= 20 &&
                                      !selectedObjectLinkIds.includes(identity))
                                  }
                                  onChange={(event) => {
                                    const selected =
                                      event.currentTarget.checked;
                                    setSelectedObjectLinkIds((current) =>
                                      toggleSelection(
                                        current,
                                        identity,
                                        selected,
                                      ),
                                    );
                                  }}
                                  type="checkbox"
                                />
                                <span>{objectLinkTypeLabel(t, link.type)}</span>
                                <span data-language-exempt="business-data">
                                  {link.code} · {link.title}
                                </span>
                                <span>
                                  {t("Version")}{" "}
                                  {formatNumber(locale, link.version, 0)}
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      </fieldset>
                    ) : null}
                  </div>
                ) : (
                  <p className="governance-help">
                    {t(
                      "No optional comment references are currently available. You can still add a body-only comment.",
                    )}
                  </p>
                )}
                {validation ? (
                  <p className="field-error" role="alert">
                    {validation}
                  </p>
                ) : null}
                <div className="detail-actions governance-form-actions">
                  <Button
                    disabled={
                      !sessionCommandContext ||
                      commandState.kind === "processing"
                    }
                    type="submit"
                    visual="primary"
                  >
                    {t("Add comment")}
                  </Button>
                </div>
              </form>
            </Panel>
          ) : null}
        </div>
        <ActivityInspector
          item={selected}
          navigate={navigate}
          projectId={projectId}
        />
      </div>
    </>
  );
}

function LearningInspector({
  learning,
}: {
  learning: ProjectLearningViewModel | undefined;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  if (!learning) {
    return (
      <DockedInspector title={t("Learning details")}>
        <p>{t("Select a learning record to inspect its immutable context.")}</p>
      </DockedInspector>
    );
  }
  return (
    <DockedInspector title={learningKindLabel(t, learning.kind)}>
      {learning.kind === "template_improvement" ? (
        <div className="scenario-banner" role="status">
          <SemanticStatus label={t("Proposed")} tone="info" />
          <span>
            {t(
              "This feedback is proposed only. It does not change or publish a Project Template.",
            )}
          </span>
        </div>
      ) : null}
      <DefinitionList
        rows={[
          {
            label: t("Title"),
            value: learning.title,
            exempt: "business-data",
          },
          {
            label: t("Learning content"),
            value: learning.content,
            exempt: "business-data",
          },
          {
            label: t("Recommendation"),
            value: learning.recommendation || t("Not provided"),
            ...(learning.recommendation
              ? ({ exempt: "business-data" } as const)
              : {}),
          },
          {
            label: t("Tags"),
            value: learning.tags.length
              ? formatList(locale, learning.tags)
              : t("None"),
            ...(learning.tags.length
              ? ({ exempt: "business-data" } as const)
              : {}),
          },
          {
            label: t("Created by"),
            value: learning.createdBy,
            exempt: "business-data",
          },
          {
            label: t("Created at"),
            value: formatDateTime(locale, learning.createdAt),
          },
          {
            label: t("Template version"),
            value: formatNumber(locale, learning.templateRef.version, 0),
          },
          {
            label: t("Template snapshot hash"),
            value: learning.templateRef.snapshotHash,
            exempt: "identifier",
          },
        ]}
      />
    </DockedInspector>
  );
}

function LearningWorkspace({
  dataSource,
  projectId,
  terminal,
}: {
  dataSource: ProjectControlsDataSource;
  projectId: string;
  terminal: boolean;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const requestedLearningId = new URLSearchParams(
    globalThis.location.search,
  ).get("learning");
  const requestedQuickCreate =
    new URLSearchParams(globalThis.location.search).get("quickCreate") ===
    "learning";
  const quickCreateTitleRef = useRef<HTMLInputElement | null>(null);
  const quickCreateFocusTransferred = useRef(false);
  const [query, setQuery] = useState<ProjectLearningQuery>({
    ...(requestedLearningId ? { learningId: requestedLearningId } : {}),
    limit: requestedLearningId ? 1 : 50,
  });
  const [filterKind, setFilterKind] = useState<"" | ProjectLearningKind>("");
  const [filterSearch, setFilterSearch] = useState("");
  const [state, setState] = useState<
    ResourceState<ProjectLearningPageViewModel>
  >({
    kind: "loading",
  });
  const [selectedId, setSelectedId] = useState("");
  const [kind, setKind] = useState<ProjectLearningKind>("retrospective");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [recommendation, setRecommendation] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [validation, setValidation] = useState<string | null>(null);
  const [commandState, setCommandState] = useState<CommandState>({
    kind: "idle",
  });
  const runner = useCommandRunner(setCommandState);

  const load = useCallback((): void => {
    runner.cancel();
    setCommandState({ kind: "idle" });
    setState({ kind: "loading" });
    setAttempt((current) => current + 1);
  }, [runner]);

  useEffect(() => {
    const controller = new AbortController();
    void dataSource
      .loadLearning(projectId, query, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setState({ kind: "loaded", value });
        setSelectedId((current) =>
          requestedLearningId &&
          value.items.some((item) => item.globalId === requestedLearningId)
            ? requestedLearningId
            : value.items.some((item) => item.globalId === current)
              ? current
              : (value.items[0]?.globalId ?? ""),
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ProjectControlsRequestCancelledError
        ) {
          return;
        }
        setState({ failure: toRequestFailure(error), kind: "failed" });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, projectId, query, requestedLearningId]);

  const quickCreateCanReceiveFocus =
    state.kind === "loaded" && state.value.permissions.canCreate;
  useEffect(() => {
    quickCreateFocusTransferred.current = false;
  }, [projectId, requestedQuickCreate]);
  useEffect(() => {
    if (
      !requestedQuickCreate ||
      !quickCreateCanReceiveFocus ||
      quickCreateFocusTransferred.current
    ) {
      return;
    }
    quickCreateFocusTransferred.current = true;
    queueMicrotask(() => {
      void focusControl(quickCreateTitleRef.current);
    });
  }, [quickCreateCanReceiveFocus, requestedQuickCreate]);

  if (state.kind === "loading") {
    return <ResourceLoading label={t("Loading project learning")} />;
  }
  if (state.kind === "failed") {
    return <ResourceFailure failure={state.failure} retry={load} />;
  }
  const page = state.value;
  const { canCreate } = page.permissions;
  const selected = page.items.find((item) => item.globalId === selectedId);

  const applyFilters = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const search = filterSearch.trim();
    setState({ kind: "loading" });
    setQuery({
      ...(filterKind ? { kind: filterKind } : {}),
      ...(search ? { search } : {}),
      limit: 50,
    });
  };

  const createLearning = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!sessionCommandContext || !canCreate) return;
    const tags = tagInput
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    if (!title.trim() || !content.trim()) {
      setValidation(t("Enter a title and learning content."));
      return;
    }
    if (
      tags.length > 20 ||
      tags.some((tag) => tag.length > 64) ||
      new Set(tags).size !== tags.length
    ) {
      setValidation(t("Enter no more than twenty unique learning tags."));
      return;
    }
    setValidation(null);
    const trimmedRecommendation = recommendation.trim();
    const command: CreateProjectLearningCommand = {
      content,
      kind,
      recommendation:
        trimmedRecommendation.length > 0 ? trimmedRecommendation : null,
      tags,
      title,
    };
    runner.run(async (contextValue) => {
      const result = await dataSource.createLearning(
        projectId,
        command,
        contextValue,
      );
      const normalizedSearch = query.search?.toLocaleLowerCase();
      const visible =
        (!query.learningId || query.learningId === result.globalId) &&
        (!query.kind || query.kind === result.kind) &&
        (normalizedSearch === undefined ||
          [result.title, result.content, result.recommendation].some((value) =>
            value.toLocaleLowerCase().includes(normalizedSearch),
          ));
      setState({
        kind: "loaded",
        value: {
          ...page,
          items: visible ? [result, ...page.items] : page.items,
        },
      });
      setSelectedId(visible ? result.globalId : selectedId);
      setTitle("");
      setContent("");
      setRecommendation("");
      setTagInput("");
      setCommandState({
        kind: "succeeded",
        message: t("Append-only project learning record created."),
      });
    }, sessionCommandContext.csrfToken);
  };

  return (
    <>
      {terminal ? (
        <div className="scenario-banner" role="status">
          <SemanticStatus label={t("Append-only learning")} tone="info" />
          <span>
            {t(
              "This terminal project still accepts authorized retrospective and learning records without changing project history.",
            )}
          </span>
        </div>
      ) : null}
      {!canCreate ? (
        <div className="scenario-banner" role="status">
          <SemanticStatus label={t("Read only")} tone="info" />
          <span>
            {t("You can view learning records but cannot create them.")}
          </span>
        </div>
      ) : null}
      <CommandFeedback
        reload={load}
        retry={runner.retry}
        state={commandState}
      />
      <form className="governance-filter-bar" onSubmit={applyFilters}>
        <label>
          <span>{t("Learning kind")}</span>
          <Select
            onChange={(event) => {
              setFilterKind(
                event.currentTarget.value as "" | ProjectLearningKind,
              );
            }}
            value={filterKind}
          >
            <option value="">{t("All learning kinds")}</option>
            <option value="retrospective">{t("Retrospective")}</option>
            <option value="lesson">{t("Lesson learned")}</option>
            <option value="template_improvement">
              {t("Template improvement")}
            </option>
          </Select>
        </label>
        <label>
          <span>{t("Search learning")}</span>
          <TextInput
            maxLength={140}
            onChange={(event) => {
              setFilterSearch(event.currentTarget.value);
            }}
            value={filterSearch}
          />
        </label>
        <Button icon="filter" type="submit">
          {t("Apply filters")}
        </Button>
      </form>
      <div className="project-learning-layout">
        <div className="project-learning-main">
          <Panel title={t("Project learning")}>
            {page.items.length ? (
              <table className="data-table data-table--compact governance-learning-table">
                <thead>
                  <tr>
                    <th>{t("Kind")}</th>
                    <th>{t("Title")}</th>
                    <th>{t("Created by")}</th>
                    <th>{t("Created at")}</th>
                    <th>{t("Template version")}</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((item) => (
                    <tr
                      aria-selected={selectedId === item.globalId}
                      className={
                        selectedId === item.globalId ? "is-selected" : undefined
                      }
                      key={item.globalId}
                      onClick={() => {
                        setSelectedId(item.globalId);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedId(item.globalId);
                        }
                      }}
                      tabIndex={0}
                    >
                      <td>{learningKindLabel(t, item.kind)}</td>
                      <td data-language-exempt="business-data">{item.title}</td>
                      <td data-language-exempt="business-data">
                        {item.createdBy}
                      </td>
                      <td>
                        <time dateTime={item.createdAt}>
                          {formatDateTime(locale, item.createdAt)}
                        </time>
                      </td>
                      <td>
                        {formatNumber(locale, item.templateRef.version, 0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="table-empty">
                {t("No learning records match the current filters.")}
              </div>
            )}
          </Panel>
          {canCreate ? (
            <Panel
              id="project-learning-quick-create"
              title={t("Create learning record")}
            >
              <form onSubmit={createLearning}>
                <div className="governance-form-grid">
                  <label className="field-control">
                    <span>{t("Learning kind")}</span>
                    <Select
                      disabled={commandState.kind === "processing"}
                      onChange={(event) => {
                        setKind(
                          event.currentTarget.value as ProjectLearningKind,
                        );
                      }}
                      value={kind}
                    >
                      <option value="retrospective">
                        {t("Retrospective")}
                      </option>
                      <option value="lesson">{t("Lesson learned")}</option>
                      <option value="template_improvement">
                        {t("Template improvement")}
                      </option>
                    </Select>
                  </label>
                  <label className="field-control">
                    <span>{t("Title")}</span>
                    <TextInput
                      disabled={commandState.kind === "processing"}
                      maxLength={280}
                      onChange={(event) => {
                        setTitle(event.currentTarget.value);
                      }}
                      ref={quickCreateTitleRef}
                      required
                      value={title}
                    />
                  </label>
                </div>
                {kind === "template_improvement" ? (
                  <div className="scenario-banner" role="status">
                    <SemanticStatus label={t("Proposed")} tone="info" />
                    <span>
                      {t(
                        "This feedback is proposed only. It does not change or publish a Project Template.",
                      )}
                    </span>
                  </div>
                ) : null}
                <label className="field-control">
                  <span>{t("Learning content")}</span>
                  <textarea
                    disabled={commandState.kind === "processing"}
                    maxLength={4000}
                    onChange={(event) => {
                      setContent(event.currentTarget.value);
                    }}
                    required
                    rows={4}
                    value={content}
                  />
                </label>
                <label className="field-control">
                  <span>{t("Recommendation")}</span>
                  <textarea
                    disabled={commandState.kind === "processing"}
                    maxLength={4000}
                    onChange={(event) => {
                      setRecommendation(event.currentTarget.value);
                    }}
                    rows={3}
                    value={recommendation}
                  />
                </label>
                <label className="field-control">
                  <span>{t("Tags")}</span>
                  <TextInput
                    disabled={commandState.kind === "processing"}
                    onChange={(event) => {
                      setTagInput(event.currentTarget.value);
                    }}
                    placeholder={t("Comma-separated tags")}
                    value={tagInput}
                  />
                </label>
                <p className="governance-help">
                  {t(
                    "The exact project template version and snapshot are captured automatically.",
                  )}
                </p>
                {validation ? (
                  <p className="field-error" role="alert">
                    {validation}
                  </p>
                ) : null}
                <div className="detail-actions governance-form-actions">
                  <Button
                    disabled={
                      !sessionCommandContext ||
                      commandState.kind === "processing"
                    }
                    type="submit"
                    visual="primary"
                  >
                    {t("Create learning record")}
                  </Button>
                </div>
              </form>
            </Panel>
          ) : null}
        </div>
        <LearningInspector learning={selected} />
      </div>
    </>
  );
}

export function ProjectGovernanceWorkspace({
  cockpitState,
  dataSource,
  navigate,
  onProjectChanged,
  projectId,
  section,
}: {
  cockpitState: ProjectLifecycleState;
  dataSource?: ProjectControlsDataSource | undefined;
  navigate: (target: string) => void;
  onProjectChanged: (project: ProjectControlsViewModel["project"]) => void;
  projectId: string;
  section: ProjectGovernanceSection;
}): React.JSX.Element {
  if (!dataSource) return <MissingDataSource />;
  const terminal = cockpitState === "completed" || cockpitState === "cancelled";
  if (section === "controls") {
    return (
      <ControlsWorkspace
        cockpitState={cockpitState}
        dataSource={dataSource}
        onProjectChanged={onProjectChanged}
        projectId={projectId}
      />
    );
  }
  if (section === "activity") {
    return (
      <ActivityWorkspace
        dataSource={dataSource}
        navigate={navigate}
        projectId={projectId}
        terminal={terminal}
      />
    );
  }
  return (
    <LearningWorkspace
      dataSource={dataSource}
      projectId={projectId}
      terminal={terminal}
    />
  );
}
