import { useCallback, useEffect, useRef, useState } from "react";

import type {
  ReportWorkspaceDirty,
  RequestWorkspaceTransition,
} from "../app/workspace-navigation";
import type {
  ReadinessDataSource,
  ReadinessAssignment,
  InitializeProjectReadinessCommand,
  ReadinessInstanceRevision,
  ReadinessItemSnapshot,
  ReadinessSourceOption,
  ReadinessSourceReference,
  ReadinessSourceSelection,
  ReadinessTemplateCatalog,
  ReadinessTemplateVersion,
  ReadinessWorkspace,
  ReviseProjectReadinessItemCommand,
} from "../api/readiness-data-source";
import { ReadinessRequestCancelledError } from "../api/readiness-data-source";
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
  ProjectMemberViewModel,
  SemanticTone,
} from "../domain/view-models";
import {
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
} from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";
import { FormalQualityLinkInspector } from "./formal-quality-link-inspector";
import type { FormalQualityLinkDataSource } from "../api/formal-quality-link-data-source";

type ResourceState =
  | { kind: "loading" }
  | { kind: "loaded"; value: ReadinessWorkspace }
  | { kind: "failed"; failure: RequestFailure; projectId: string };

type CommandState =
  | { kind: "idle" }
  | { kind: "processing" }
  | { kind: "succeeded"; replayed: boolean }
  | { kind: "failed"; failure: RequestFailure };

interface ItemDraft {
  confirmationValue: string;
  dueDate: string;
  ownerMemberGlobalId: string;
  selectedOptionKeys: readonly string[];
  state: "not_started" | "in_progress" | "complete" | "failed";
}

interface RetryableCommand {
  readonly command: ReviseProjectReadinessItemCommand;
  readonly idempotencyKey: string;
  readonly instanceId: string;
}

interface InitializationAssignmentDraft {
  readonly dueDate: string;
  readonly ownerMemberGlobalId: string;
}

interface InitializationDraft {
  readonly assignments: Readonly<Record<string, InitializationAssignmentDraft>>;
  readonly industryKey: string;
  readonly templateRevisionGlobalId: string;
}

interface RetryableInitialization {
  readonly command: InitializeProjectReadinessCommand;
  readonly idempotencyKey: string;
}

function itemStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: ReadinessItemSnapshot["state"],
): string {
  switch (state) {
    case "not_started":
      return t("Not started");
    case "in_progress":
      return t("In progress");
    case "complete":
      return t("Complete");
    case "failed":
      return t("Failed");
    case "not_applicable":
      return t("Not applicable");
  }
}

function itemStateTone(state: ReadinessItemSnapshot["state"]): SemanticTone {
  switch (state) {
    case "complete":
      return "success";
    case "failed":
      return "danger";
    case "in_progress":
      return "info";
    case "not_started":
      return "warning";
    case "not_applicable":
      return "neutral";
  }
}

function sourceStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: ReadinessSourceReference["state"],
): string {
  switch (state) {
    case "satisfied":
      return t("Satisfied");
    case "failed":
      return t("Failed");
    case "unavailable":
      return t("Unavailable");
  }
}

function sourceStateTone(
  state: ReadinessSourceReference["state"],
): SemanticTone {
  if (state === "satisfied") return "success";
  if (state === "failed") return "danger";
  return "warning";
}

function sourceKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: ReadinessSourceReference["kind"],
): string {
  switch (kind) {
    case "project":
      return t("Project snapshot");
    case "domain_work_item":
      return t("Project work item");
    case "released_document":
      return t("Released document");
    case "release_baseline":
      return t("Release baseline");
    case "file_revision":
      return t("File revision");
    case "tooling_capacity_scenario":
      return t("Tooling capacity scenario");
    case "trial_input_lock":
      return t("Trial input lock");
    case "trial_actual":
      return t("Trial actual");
    case "trial_sample":
      return t("Trial sample");
    case "trial_cavity_result":
      return t("Trial cavity result");
    case "trial_defect":
      return t("Trial defect");
    case "trial_defect_verification":
      return t("Trial defect verification");
    case "trial_comparison":
      return t("Trial comparison");
    case "trial_review_reference":
      return t("Trial review reference");
    case "trial_conclusion":
      return t("Trial conclusion");
    case "controlled_quality_result":
      return t("Controlled quality result");
    case "erp_material_specification":
      return t("Formal ERP material specification");
    case "erp_quality_result":
      return t("Formal ERP quality result");
    case "erp_run_at_rate":
      return t("Formal ERP run-at-rate result");
    case "erp_hr_qualification":
      return t("Formal HR qualification");
    case "erp_supplier_execution":
      return t("Formal ERP supplier execution");
  }
}

function blockerLabel(
  t: ReturnType<typeof useI18n>["t"],
  code: ReadinessInstanceRevision["evaluation"]["blockers"][number]["code"],
): string {
  switch (code) {
    case "incomplete_p0":
      return t("Incomplete P0 item");
    case "failed_mandatory_quality":
      return t("Failed mandatory quality result");
    case "required_source_unavailable":
      return t("Required source unavailable");
  }
}

function completionRuleLabel(
  t: ReturnType<typeof useI18n>["t"],
  rule: ReadinessItemSnapshot["definition"]["completionRule"],
): string {
  switch (rule) {
    case "confirmation":
      return t("Controlled confirmation");
    case "exact_evidence":
      return t("Exact evidence");
    case "exact_source_result":
      return t("Exact source result");
  }
}

function sourceOptionStateLabel(
  t: ReturnType<typeof useI18n>["t"],
  source: ReadinessSourceOption["stateLabelSource"],
): string {
  switch (source) {
    case "Draft":
      return t("Draft");
    case "Identified":
      return t("Identified");
    case "Not started":
      return t("Not started");
    case "Open":
      return t("Open");
    case "Requested":
      return t("Requested");
  }
}

function externalUnavailableReason(
  t: ReturnType<typeof useI18n>["t"],
  reasonCode: string,
): string {
  switch (reasonCode) {
    case "erp_material_specification_provider_unavailable":
      return t(
        "The formal ERP material specification provider is unavailable.",
      );
    case "erp_quality_result_provider_unavailable":
      return t("The formal ERP quality provider is unavailable.");
    case "erp_run_at_rate_provider_unavailable":
      return t("The formal ERP run-at-rate provider is unavailable.");
    case "erp_hr_qualification_provider_unavailable":
      return t("The formal HR qualification provider is unavailable.");
    case "erp_supplier_execution_provider_unavailable":
      return t("The formal ERP supplier execution provider is unavailable.");
    default:
      return t("The formal source provider is unavailable.");
  }
}

function scoreValue(
  locale: ReturnType<typeof useI18n>["locale"],
  t: ReturnType<typeof useI18n>["t"],
  basisPoints: number | null,
): string {
  return basisPoints === null
    ? t("Not applicable")
    : formatPercent(locale, basisPoints / 10_000);
}

function optionKey(
  requirementKey: string,
  option: ReadinessSourceOption,
): string {
  return [
    requirementKey,
    option.kind,
    option.globalId,
    String(option.sourceVersion),
    option.snapshotHash,
  ].join("|");
}

function exactOptionMatches(
  source: ReadinessSourceReference,
  option: ReadinessSourceOption,
): boolean {
  return (
    source.kind === "domain_work_item" &&
    source.globalId === option.globalId &&
    source.sourceVersion === option.sourceVersion &&
    source.snapshotHash === option.snapshotHash
  );
}

function itemDraft(
  item: ReadinessItemSnapshot,
  options: readonly ReadinessSourceOption[],
): ItemDraft {
  const selectedOptionKeys = item.sources.flatMap((source) => {
    const option = options.find((candidate) =>
      exactOptionMatches(source, candidate),
    );
    return option ? [optionKey(source.requirementKey, option)] : [];
  });
  return {
    confirmationValue: item.confirmationValue ?? "",
    dueDate: item.dueDate ?? "",
    ownerMemberGlobalId: item.owner?.globalId ?? "",
    selectedOptionKeys,
    state: item.state === "not_applicable" ? "not_started" : item.state,
  };
}

function supportsBrowserInitialization(
  template: ReadinessTemplateVersion,
): boolean {
  return template.items.every(
    (item) =>
      item.applicability.projectTypes.length === 0 &&
      item.applicability.customerReferenceKeys.length === 0,
  );
}

function templateMatchesIndustry(
  template: ReadinessTemplateVersion,
  industryKey: string,
): boolean {
  return (
    template.applicability.industryKeys.length === 0 ||
    template.applicability.industryKeys.includes(industryKey)
  );
}

function industryApplicableItems(
  template: ReadinessTemplateVersion,
  industryKey: string,
): readonly ReadinessTemplateVersion["items"][number][] {
  return template.items.filter(
    (item) =>
      item.applicability.industryKeys.length === 0 ||
      item.applicability.industryKeys.includes(industryKey),
  );
}

function exactProjectMembers(
  members: readonly ProjectMemberViewModel[],
  projectId: string,
): readonly ProjectMemberViewModel[] {
  const contained = members.filter((member) => member.projectId === projectId);
  const identities = contained.map((member) => member.globalId);
  return new Set(identities).size === identities.length ? contained : [];
}

function sameDraft(left: ItemDraft | null, right: ItemDraft | null): boolean {
  if (!left || !right) return left === right;
  return (
    left.confirmationValue === right.confirmationValue &&
    left.dueDate === right.dueDate &&
    left.ownerMemberGlobalId === right.ownerMemberGlobalId &&
    left.state === right.state &&
    [...left.selectedOptionKeys].sort().join("|") ===
      [...right.selectedOptionKeys].sort().join("|")
  );
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

function LoadingState(): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section
      aria-busy="true"
      aria-label={t("Loading NPI readiness")}
      className="workspace-resource-state workspace-resource-state--loading"
      data-testid="readiness-loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">{t("Loading NPI readiness")}</span>
    </section>
  );
}

function FailureState({
  failure,
  onRetry,
}: {
  failure: RequestFailure;
  onRetry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  const denied =
    failure.problem?.status === 401 || failure.problem?.status === 403;
  const drift = failure.problem?.status === 409;
  return (
    <section
      className="workspace-resource-state"
      data-testid="readiness-error"
      role="alert"
    >
      <SemanticStatus
        label={
          denied ? t("No permission") : drift ? t("Input drift") : t("Error")
        }
        tone={drift ? "warning" : "danger"}
      />
      <h2>
        {denied
          ? t("NPI readiness access is not available")
          : drift
            ? t("The NPI readiness workspace is out of date")
            : t("NPI readiness data is unavailable")}
      </h2>
      <p>
        {denied
          ? t("No protected readiness data was displayed.")
          : drift
            ? t("Reload the exact retained revision before continuing.")
            : t("Use the reference ID for support or retry when available.")}
      </p>
      <RequestFailurePanel failure={failure} />
      {canRetry(failure) ? (
        <Button icon="refresh" onClick={onRetry}>
          {drift ? t("Reload latest data") : t("Retry")}
        </Button>
      ) : null}
    </section>
  );
}

function EmptyState({
  dataSource,
  members,
  onInitialized,
  projectId,
  reportWorkspaceDirty,
  workspace,
}: {
  dataSource: ReadinessDataSource;
  members: readonly ProjectMemberViewModel[];
  onInitialized: (workspace: ReadinessWorkspace, replayed: boolean) => void;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  workspace: ReadinessWorkspace;
}): React.JSX.Element {
  const { sessionCommandContext, t } = useI18n();
  const [catalogAttempt, setCatalogAttempt] = useState(0);
  const [catalogState, setCatalogState] = useState<
    | { kind: "idle" }
    | { kind: "loading" }
    | { kind: "loaded"; value: ReadinessTemplateCatalog }
    | { kind: "failed"; failure: RequestFailure }
  >({ kind: workspace.permissions.canInitialize ? "loading" : "idle" });
  const [draft, setDraft] = useState<InitializationDraft>({
    assignments: {},
    industryKey: "",
    templateRevisionGlobalId: "",
  });
  const [validation, setValidation] = useState<string | null>(null);
  const [commandState, setCommandState] = useState<CommandState>({
    kind: "idle",
  });
  const [review, setReview] = useState<RetryableInitialization | null>(null);
  const commandController = useRef<AbortController | null>(null);
  const retryCommand = useRef<RetryableInitialization | null>(null);
  const trigger = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!workspace.permissions.canInitialize) {
      return undefined;
    }
    const controller = new AbortController();
    void dataSource
      .listEligibleTemplates(projectId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted)
          setCatalogState({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ReadinessRequestCancelledError
        )
          return;
        setCatalogState({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [
    catalogAttempt,
    dataSource,
    projectId,
    workspace.permissions.canInitialize,
  ]);

  useEffect(
    () => () => {
      commandController.current?.abort();
    },
    [],
  );

  const availableProjectMembers = exactProjectMembers(members, projectId);
  const catalog = catalogState.kind === "loaded" ? catalogState.value : null;
  const selectedTemplate =
    catalog?.templates.find(
      (template) => template.globalId === draft.templateRevisionGlobalId,
    ) ?? null;
  const selectedTemplateSupported = Boolean(
    selectedTemplate && supportsBrowserInitialization(selectedTemplate),
  );
  const applicableItems = selectedTemplate
    ? industryApplicableItems(selectedTemplate, draft.industryKey)
    : [];
  const dirty = Boolean(
    draft.templateRevisionGlobalId ||
    draft.industryKey ||
    Object.values(draft.assignments).some(
      (assignment) => assignment.ownerMemberGlobalId || assignment.dueDate,
    ),
  );

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!dirty) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: `${projectId}:readiness-initialization`,
      returnFocusTarget: () =>
        trigger.current ??
        document.getElementById("project-workspace-tab-readiness"),
      version: "unsaved-readiness-initialization",
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [dirty, projectId, reportWorkspaceDirty]);

  const execute = useCallback(
    (operation: RetryableInitialization): void => {
      if (!sessionCommandContext) return;
      commandController.current?.abort();
      const controller = new AbortController();
      commandController.current = controller;
      setCommandState({ kind: "processing" });
      void dataSource
        .initialize(projectId, operation.command, {
          csrfToken: sessionCommandContext.csrfToken,
          idempotencyKey: operation.idempotencyKey,
          signal: controller.signal,
        })
        .then((result) => {
          if (controller.signal.aborted) return;
          retryCommand.current = null;
          reportWorkspaceDirty?.(null);
          onInitialized(result.workspace, result.replayed);
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            error instanceof ReadinessRequestCancelledError
          )
            return;
          setCommandState({ kind: "failed", failure: toRequestFailure(error) });
        });
    },
    [
      dataSource,
      onInitialized,
      projectId,
      reportWorkspaceDirty,
      sessionCommandContext,
    ],
  );

  const prepare = (): void => {
    if (!selectedTemplate) {
      setValidation(t("Select an exact published readiness template version."));
      return;
    }
    if (!supportsBrowserInitialization(selectedTemplate)) {
      setValidation(
        t(
          "This template uses Project or customer item selectors that this browser cannot resolve safely.",
        ),
      );
      return;
    }
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u.test(draft.industryKey)) {
      setValidation(t("Enter a valid industry key."));
      return;
    }
    if (!templateMatchesIndustry(selectedTemplate, draft.industryKey)) {
      setValidation(
        t("The selected template does not apply to this industry key."),
      );
      return;
    }
    const items = industryApplicableItems(selectedTemplate, draft.industryKey);
    if (!items.length) {
      setValidation(t("No readiness items apply to this industry key."));
      return;
    }
    if (!availableProjectMembers.length) {
      setValidation(t("No exact Project members are available."));
      return;
    }
    const assignments: ReadinessAssignment[] = [];
    for (const item of items) {
      const assignment = draft.assignments[item.key];
      if (!assignment?.ownerMemberGlobalId || !assignment.dueDate) {
        setValidation(
          t("Assign an owner and due date to every applicable item."),
        );
        return;
      }
      if (
        !availableProjectMembers.some(
          (member) => member.globalId === assignment.ownerMemberGlobalId,
        )
      ) {
        setValidation(t("Select an exact Project member."));
        return;
      }
      assignments.push({
        dueDate: assignment.dueDate,
        itemKey: item.key,
        ownerMemberGlobalId: assignment.ownerMemberGlobalId,
      });
    }
    const operation: RetryableInitialization = {
      command: {
        assignments,
        industryKey: draft.industryKey,
        templateRevisionGlobalId: selectedTemplate.globalId,
        templateSnapshotHash: selectedTemplate.snapshotHash,
        templateVersion: selectedTemplate.templateVersion,
      },
      idempotencyKey: `readiness-initialize-${globalThis.crypto.randomUUID()}`,
    };
    retryCommand.current = operation;
    setValidation(null);
    setReview(operation);
  };

  return (
    <div className="readiness-workspace__empty" data-testid="readiness-empty">
      <Panel title={t("NPI readiness has not been initialized")}>
        <SemanticStatus label={t("No retained instance")} tone="warning" />
        <p>
          {t(
            "No readiness score or blocker state is shown until an authorized administrator initializes an exact published template.",
          )}
        </p>
        {!workspace.permissions.canInitialize ? (
          <p>{t("You have read-only access to this workspace.")}</p>
        ) : catalogState.kind === "loading" ? (
          <div aria-busy="true" role="status">
            <span>{t("Loading eligible readiness templates")}</span>
          </div>
        ) : catalogState.kind === "failed" ? (
          <div role="alert">
            <SemanticStatus
              label={t("Template catalog unavailable")}
              tone="danger"
            />
            <RequestFailurePanel failure={catalogState.failure} />
            {canRetry(catalogState.failure) ? (
              <Button
                icon="refresh"
                onClick={() => {
                  setCatalogState({ kind: "loading" });
                  setCatalogAttempt((value) => value + 1);
                }}
              >
                {t("Retry")}
              </Button>
            ) : null}
          </div>
        ) : catalog && !catalog.templates.length ? (
          <div role="status">
            <SemanticStatus
              label={t("No eligible published readiness template")}
              tone="warning"
            />
            <p>
              {t(
                "An administrator must publish an applicable template before this Project can be initialized.",
              )}
            </p>
          </div>
        ) : catalog &&
          !catalog.templates.some((template) =>
            supportsBrowserInitialization(template),
          ) ? (
          <div role="status">
            <SemanticStatus
              label={t("No safely initializable readiness template")}
              tone="warning"
            />
            <p>
              {t(
                "Eligible templates use Project or customer item selectors that this browser cannot resolve safely. No initialization command is available.",
              )}
            </p>
          </div>
        ) : !availableProjectMembers.length ? (
          <div role="status">
            <SemanticStatus
              label={t("No Project members available")}
              tone="warning"
            />
            <p>
              {t(
                "Initialization is blocked until an exact member is available in this Project.",
              )}
            </p>
          </div>
        ) : catalog ? (
          <form
            className="readiness-workspace__initialize"
            onSubmit={(event) => {
              event.preventDefault();
              trigger.current =
                event.currentTarget.querySelector("ix-button, button");
              prepare();
            }}
          >
            <label>
              <span>{t("Published readiness template")}</span>
              <Select
                data-testid="readiness-template"
                onChange={(event) => {
                  const template = catalog.templates.find(
                    (candidate) =>
                      candidate.globalId === event.currentTarget.value,
                  );
                  const assignments = Object.fromEntries(
                    (template
                      ? industryApplicableItems(template, draft.industryKey)
                      : []
                    ).map((item) => [
                      item.key,
                      { dueDate: "", ownerMemberGlobalId: "" },
                    ]),
                  );
                  setDraft({
                    assignments,
                    industryKey: draft.industryKey,
                    templateRevisionGlobalId: event.currentTarget.value,
                  });
                  setValidation(null);
                }}
                required
                value={draft.templateRevisionGlobalId}
              >
                <option value="">{t("Select published template")}</option>
                {catalog.templates.map((template) => (
                  <option
                    data-language-exempt-tokens={JSON.stringify([
                      template.title,
                    ])}
                    disabled={!supportsBrowserInitialization(template)}
                    key={template.globalId}
                    value={template.globalId}
                  >
                    {supportsBrowserInitialization(template)
                      ? template.title
                      : t("{{template}} — browser initialization unavailable", {
                          template: template.title,
                        })}
                  </option>
                ))}
              </Select>
            </label>
            <label>
              <span>{t("Industry key")}</span>
              <TextInput
                data-testid="readiness-industry-key"
                maxLength={128}
                onChange={(event) => {
                  setDraft({
                    ...draft,
                    industryKey: event.currentTarget.value,
                  });
                  setValidation(null);
                }}
                pattern="[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
                required
                value={draft.industryKey}
              />
            </label>
            {selectedTemplate && selectedTemplateSupported ? (
              <fieldset data-testid="readiness-assignments">
                <legend>{t("Exact item assignments")}</legend>
                <p>
                  {t(
                    "The server confirms final item applicability from the frozen Project context.",
                  )}
                </p>
                <table className="engineering-table engineering-table--compact">
                  <thead>
                    <tr>
                      <th scope="col">{t("Item")}</th>
                      <th scope="col">{t("Owner")}</th>
                      <th scope="col">{t("Due date")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {applicableItems.map((item) => {
                      const assignment = draft.assignments[item.key] ?? {
                        dueDate: "",
                        ownerMemberGlobalId: "",
                      };
                      return (
                        <tr key={item.key}>
                          <th data-language-exempt="business-data" scope="row">
                            {item.title}
                          </th>
                          <td>
                            <Select
                              aria-label={t("Owner for {{item}}", {
                                item: item.title,
                              })}
                              data-language-exempt="business-data"
                              data-testid={`readiness-assignment-owner-${item.key}`}
                              onChange={(event) => {
                                setDraft({
                                  ...draft,
                                  assignments: {
                                    ...draft.assignments,
                                    [item.key]: {
                                      ...assignment,
                                      ownerMemberGlobalId:
                                        event.currentTarget.value,
                                    },
                                  },
                                });
                                setValidation(null);
                              }}
                              required
                              value={assignment.ownerMemberGlobalId}
                            >
                              <option value="">{t("Select owner")}</option>
                              {availableProjectMembers.map((member) => (
                                <option
                                  key={member.globalId}
                                  value={member.globalId}
                                >
                                  {member.userId}
                                </option>
                              ))}
                            </Select>
                          </td>
                          <td>
                            <TextInput
                              aria-label={t("Due date for {{item}}", {
                                item: item.title,
                              })}
                              data-testid={`readiness-assignment-due-${item.key}`}
                              onChange={(event) => {
                                setDraft({
                                  ...draft,
                                  assignments: {
                                    ...draft.assignments,
                                    [item.key]: {
                                      ...assignment,
                                      dueDate: event.currentTarget.value,
                                    },
                                  },
                                });
                                setValidation(null);
                              }}
                              required
                              type="date"
                              value={assignment.dueDate}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </fieldset>
            ) : null}
            {validation ? (
              <p className="form-error" role="alert">
                {validation}
              </p>
            ) : null}
            <Button
              data-testid="readiness-initialize"
              disabled={
                !sessionCommandContext ||
                !selectedTemplate ||
                commandState.kind === "processing"
              }
              type="submit"
              visual="primary"
            >
              {t("Review readiness initialization")}
            </Button>
            {!sessionCommandContext ? (
              <p>
                {t("Session verification is required before initialization.")}
              </p>
            ) : null}
          </form>
        ) : null}
        <CommandFeedback
          onReload={() => {
            setCatalogState({ kind: "loading" });
            setCatalogAttempt((value) => value + 1);
          }}
          onRetry={() => {
            if (retryCommand.current) execute(retryCommand.current);
          }}
          operation="initialize"
          state={commandState}
        />
      </Panel>
      <UnavailableProjectionPanel workspace={workspace} />
      {review && selectedTemplate ? (
        <ImpactReview
          confirmLabel={t("Initialize NPI readiness")}
          contextRows={[
            {
              exempt: "business-data",
              label: t("Template"),
              value: selectedTemplate.title,
            },
            {
              exempt: "identifier",
              label: t("Template revision"),
              value: selectedTemplate.globalId,
            },
            {
              exempt: "identifier",
              label: t("Industry key"),
              value: review.command.industryKey,
            },
          ]}
          details={{
            audit: t(
              "The command, receipt, actor and exact snapshot are audited atomically.",
            ),
            failureHandling: t(
              "A failure creates no partial instance. Retry uses the same command identity.",
            ),
            impact: t(
              "Creates revision 1 from the exact published template and frozen Project context.",
            ),
            irreversible: t(
              "The retained readiness instance and its revision history cannot be overwritten.",
            ),
            objectIdentity: projectId,
            permission: t("An enabled internal System Manager is required."),
            version: t("New readiness instance"),
          }}
          onCancel={() => {
            setReview(null);
          }}
          onConfirm={() => {
            setReview(null);
            execute(review);
          }}
          reasonRequired={false}
          returnFocusTarget={() => trigger.current}
          title={t("Review readiness initialization")}
        />
      ) : null}
    </div>
  );
}

function UnavailableProjectionPanel({
  workspace,
}: {
  workspace: ReadinessWorkspace;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <Panel
      className="readiness-workspace__unavailable"
      title={t("Unavailable formal sources")}
    >
      <div data-testid="readiness-unavailable-projections">
        <p>
          {t(
            "These formal projections are explicit holds. This workspace performs no ERP or external network call.",
          )}
        </p>
        <table className="engineering-table engineering-table--compact">
          <thead>
            <tr>
              <th scope="col">{t("Source")}</th>
              <th scope="col">{t("State")}</th>
              <th scope="col">{t("Reason")}</th>
            </tr>
          </thead>
          <tbody>
            {workspace.unavailableProjections.map((projection) => (
              <tr key={projection.kind}>
                <td>{sourceKindLabel(t, projection.kind)}</td>
                <td>
                  <SemanticStatus label={t("Unavailable")} tone="warning" />
                </td>
                <td>{externalUnavailableReason(t, projection.reasonCode)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function CommandFeedback({
  onReload,
  onRetry,
  operation,
  state,
}: {
  onReload: () => void;
  onRetry: () => void;
  operation: "initialize" | "revise";
  state: CommandState;
}): React.JSX.Element | null {
  const { t } = useI18n();
  if (state.kind === "idle") return null;
  if (state.kind === "processing") {
    return (
      <div
        aria-live="polite"
        className="readiness-workspace__command-state"
        data-testid="readiness-processing"
        role="status"
      >
        <SemanticStatus label={t("Processing")} tone="info" />
        <span>
          {operation === "initialize"
            ? t("Initializing exact Project readiness")
            : t("Saving exact readiness revision")}
        </span>
      </div>
    );
  }
  if (state.kind === "succeeded") {
    return (
      <div
        aria-live="polite"
        className="readiness-workspace__command-state"
        data-testid={state.replayed ? "readiness-replay-receipt" : undefined}
        role="status"
      >
        <SemanticStatus label={t("Succeeded")} tone="success" />
        <span>
          {state.replayed
            ? t("The server replayed the sealed readiness response.")
            : operation === "initialize"
              ? t("The exact Project readiness instance was initialized.")
              : t("The exact readiness revision was saved.")}
        </span>
      </div>
    );
  }
  const drift = state.failure.problem?.status === 409;
  const validation = state.failure.problem?.status === 422;
  return (
    <div className="readiness-workspace__command-state" role="alert">
      <SemanticStatus
        label={
          drift
            ? t("Input drift")
            : validation
              ? t("Validation failed")
              : t("Command failed")
        }
        tone={drift ? "warning" : "danger"}
      />
      {drift ? (
        <p>
          {t(
            "The retained readiness revision changed. Reload before editing again.",
          )}
        </p>
      ) : null}
      <RequestFailurePanel failure={state.failure} />
      <div className="detail-actions">
        {canRetrySameCommand(state.failure) ? (
          <Button onClick={onRetry}>{t("Retry same command")}</Button>
        ) : null}
        <Button icon="refresh" onClick={onReload}>
          {t("Reload latest data")}
        </Button>
      </div>
    </div>
  );
}

function sourceSelection(
  source: ReadinessSourceReference,
): ReadinessSourceSelection {
  if (
    source.globalId !== null &&
    source.sourceVersion !== null &&
    source.snapshotHash !== null
  ) {
    return {
      globalId: source.globalId,
      kind: source.kind,
      requirementKey: source.requirementKey,
      snapshotHash: source.snapshotHash,
      sourceVersion: source.sourceVersion,
    };
  }
  return {
    kind: source.kind,
    requirementKey: source.requirementKey,
  } as ReadinessSourceSelection;
}

function commandSources(
  item: ReadinessItemSnapshot,
  draft: ItemDraft,
  options: readonly ReadinessSourceOption[],
): readonly ReadinessSourceSelection[] {
  const preserved = item.sources
    .filter(
      (source) => !options.some((option) => exactOptionMatches(source, option)),
    )
    .map(sourceSelection);
  const selected = item.definition.evidenceRequirements.flatMap(
    (requirement) =>
      requirement.acceptedSourceKinds.includes("domain_work_item")
        ? options.flatMap((option) =>
            draft.selectedOptionKeys.includes(
              optionKey(requirement.key, option),
            )
              ? [
                  {
                    globalId: option.globalId,
                    kind: option.kind,
                    requirementKey: requirement.key,
                    snapshotHash: option.snapshotHash,
                    sourceVersion: option.sourceVersion,
                  } satisfies ReadinessSourceSelection,
                ]
              : [],
          )
        : [],
  );
  return [...preserved, ...selected];
}

function exactSourceLabel(
  source: ReadinessSourceReference,
  options: readonly ReadinessSourceOption[],
): string | null {
  if (source.kind !== "domain_work_item") return null;
  return (
    options.find((option) => exactOptionMatches(source, option))?.label ?? null
  );
}

function ItemInspector({
  commandState,
  draft,
  draftChanged,
  historical,
  item,
  members,
  onDraftChange,
  onReload,
  onRetryCommand,
  onSave,
  readOnly,
  sourceOptions,
  validation,
}: {
  commandState: CommandState;
  draft: ItemDraft | null;
  draftChanged: boolean;
  historical: boolean;
  item: ReadinessItemSnapshot | null;
  members: readonly ProjectMemberViewModel[];
  onDraftChange: (draft: ItemDraft) => void;
  onReload: () => void;
  onRetryCommand: () => void;
  onSave: () => void;
  readOnly: boolean;
  sourceOptions: readonly ReadinessSourceOption[];
  validation: string | null;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  if (!item) {
    return (
      <DockedInspector
        id="readiness-item-inspector"
        title={t("Readiness item")}
      >
        <p>
          {t("Select a readiness item to inspect its exact retained facts.")}
        </p>
      </DockedInspector>
    );
  }
  const editable =
    !historical &&
    !readOnly &&
    item.applicable &&
    item.state !== "not_applicable" &&
    sessionCommandContext !== null;
  const ownerLabel = item.owner?.userId ?? t("Unassigned");
  const dueLabel = item.dueDate
    ? formatDate(locale, item.dueDate)
    : t("Not available");
  return (
    <DockedInspector id="readiness-item-inspector" title={t("Readiness item")}>
      <div data-testid="readiness-item-inspector">
        {historical ? (
          <SemanticStatus label={t("Historical revision")} tone="neutral" />
        ) : readOnly ? (
          <SemanticStatus label={t("Read-only workspace")} tone="warning" />
        ) : null}
        <h3 data-language-exempt="business-data">{item.definition.title}</h3>
        <DefinitionList
          rows={[
            {
              label: t("Item key"),
              value: item.definition.key,
              exempt: "identifier",
            },
            { label: t("Status"), value: itemStateLabel(t, item.state) },
            {
              label: t("Owner"),
              value: ownerLabel,
              ...(item.owner ? { exempt: "business-data" as const } : {}),
            },
            { label: t("Due date"), value: dueLabel },
            {
              label: t("Gate"),
              value: item.gate.gateKey,
              exempt: "identifier",
            },
            {
              label: t("Weight"),
              value: formatNumber(locale, item.definition.weight),
            },
            {
              label: t("Blocking level"),
              value: item.definition.blockingLevel,
              exempt: "identifier",
            },
            {
              label: t("Completion rule"),
              value: completionRuleLabel(t, item.definition.completionRule),
            },
            {
              label: t("Item version"),
              value: formatNumber(locale, item.itemVersion),
            },
          ]}
        />
        <section aria-labelledby={`readiness-evidence-${item.globalId}`}>
          <h3 id={`readiness-evidence-${item.globalId}`}>
            {t("Exact evidence")}
          </h3>
          {item.sources.length ? (
            <ul className="readiness-workspace__source-list">
              {item.sources.map((source, index) => {
                const label = exactSourceLabel(source, sourceOptions);
                return (
                  <li
                    data-testid={`readiness-source-${source.requirementKey}-${source.kind}`}
                    key={`${source.requirementKey}:${source.kind}:${source.globalId ?? "unavailable"}:${String(index)}`}
                  >
                    <div>
                      <strong>{sourceKindLabel(t, source.kind)}</strong>{" "}
                      <SemanticStatus
                        label={sourceStateLabel(t, source.state)}
                        tone={sourceStateTone(source.state)}
                      />
                    </div>
                    {label ? (
                      <div data-language-exempt="business-data">{label}</div>
                    ) : null}
                    <div>
                      <span>{t("Requirement")}: </span>
                      <code data-language-exempt="identifier">
                        {source.requirementKey}
                      </code>
                    </div>
                    {source.globalId ? (
                      <div>
                        <code data-language-exempt="identifier">
                          {source.globalId}
                        </code>{" "}
                        <span>
                          {t("Version {{version}}", {
                            version: source.sourceVersion ?? 0,
                          })}
                        </span>
                      </div>
                    ) : null}
                    {source.reasonCode ? (
                      <div>
                        <span>{t("Reason code")}: </span>
                        <code data-language-exempt="identifier">
                          {source.reasonCode}
                        </code>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p>{t("No exact evidence is retained for this item.")}</p>
          )}
        </section>
        {editable && draft ? (
          <form
            className="readiness-workspace__editor"
            onSubmit={(event) => {
              event.preventDefault();
              onSave();
            }}
          >
            <h3>{t("Revise exact item")}</h3>
            {members.length ? (
              <label>
                <span>{t("Owner")}</span>
                <Select
                  data-language-exempt="business-data"
                  data-testid="readiness-owner"
                  onChange={(event) => {
                    onDraftChange({
                      ...draft,
                      ownerMemberGlobalId: event.currentTarget.value,
                    });
                  }}
                  required
                  value={draft.ownerMemberGlobalId}
                >
                  <option value="">{t("Select owner")}</option>
                  {item.owner &&
                  !members.some(
                    (member) => member.globalId === item.owner?.globalId,
                  ) ? (
                    <option value={item.owner.globalId}>
                      {item.owner.userId}
                    </option>
                  ) : null}
                  {members.map((member) => (
                    <option key={member.globalId} value={member.globalId}>
                      {member.userId}
                    </option>
                  ))}
                </Select>
              </label>
            ) : (
              <div className="readiness-workspace__owner-hold" role="status">
                <strong>{t("No exact owner candidates")}</strong>
                <p>
                  <span>{t("Retained owner")}: </span>
                  <span data-language-exempt="business-data">{ownerLabel}</span>
                </p>
              </div>
            )}
            <label>
              <span>{t("Due date")}</span>
              <TextInput
                data-testid="readiness-due-date"
                onChange={(event) => {
                  onDraftChange({
                    ...draft,
                    dueDate: event.currentTarget.value,
                  });
                }}
                required
                type="date"
                value={draft.dueDate}
              />
            </label>
            <label>
              <span>{t("Item state")}</span>
              <Select
                data-testid="readiness-state"
                onChange={(event) => {
                  onDraftChange({
                    ...draft,
                    state: event.currentTarget.value as ItemDraft["state"],
                  });
                }}
                value={draft.state}
              >
                <option value="not_started">{t("Not started")}</option>
                <option value="in_progress">{t("In progress")}</option>
                <option value="complete">{t("Complete")}</option>
                <option value="failed">{t("Failed")}</option>
              </Select>
            </label>
            <label>
              <span>{t("Confirmation")}</span>
              <textarea
                className="npi-input"
                data-testid="readiness-confirmation"
                maxLength={4000}
                onChange={(event) => {
                  onDraftChange({
                    ...draft,
                    confirmationValue: event.currentTarget.value,
                  });
                }}
                rows={3}
                value={draft.confirmationValue}
              />
            </label>
            <fieldset data-testid="readiness-source-options">
              <legend>{t("Exact Work Item sources")}</legend>
              {item.definition.evidenceRequirements.some((requirement) =>
                requirement.acceptedSourceKinds.includes("domain_work_item"),
              ) ? (
                item.definition.evidenceRequirements.flatMap((requirement) =>
                  requirement.acceptedSourceKinds.includes("domain_work_item")
                    ? sourceOptions.map((option) => {
                        const key = optionKey(requirement.key, option);
                        return (
                          <label key={key}>
                            <input
                              checked={draft.selectedOptionKeys.includes(key)}
                              onChange={(event) => {
                                const next = event.currentTarget.checked
                                  ? [...draft.selectedOptionKeys, key]
                                  : draft.selectedOptionKeys.filter(
                                      (selected) => selected !== key,
                                    );
                                onDraftChange({
                                  ...draft,
                                  selectedOptionKeys: next,
                                });
                              }}
                              type="checkbox"
                            />
                            <span data-language-exempt="business-data">
                              {option.label}
                            </span>{" "}
                            <span>
                              {sourceOptionStateLabel(
                                t,
                                option.stateLabelSource,
                              )}
                            </span>{" "}
                            <code data-language-exempt="identifier">
                              {requirement.key}
                            </code>
                          </label>
                        );
                      })
                    : [],
                )
              ) : (
                <p>
                  {t(
                    "This item has no server-offered Work Item source selection.",
                  )}
                </p>
              )}
            </fieldset>
            {validation ? (
              <p className="form-error" role="alert">
                {validation}
              </p>
            ) : null}
            <Button
              data-testid="readiness-revise"
              disabled={commandState.kind === "processing" || !draftChanged}
              type="submit"
              visual="primary"
            >
              {t("Review readiness revision")}
            </Button>
          </form>
        ) : null}
        <CommandFeedback
          onReload={onReload}
          onRetry={onRetryCommand}
          operation="revise"
          state={commandState}
        />
      </div>
    </DockedInspector>
  );
}

export interface ProjectReadinessWorkspaceProps {
  readonly dataSource: ReadinessDataSource;
  readonly formalQualityDataSource?: FormalQualityLinkDataSource | undefined;
  readonly members: readonly ProjectMemberViewModel[];
  readonly projectId: string;
  readonly reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  readonly requestWorkspaceTransition?: RequestWorkspaceTransition | undefined;
}

export function ProjectReadinessWorkspace({
  dataSource,
  formalQualityDataSource,
  members,
  projectId,
  reportWorkspaceDirty,
  requestWorkspaceTransition,
}: ProjectReadinessWorkspaceProps): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(
    null,
  );
  const [selectedCategoryKey, setSelectedCategoryKey] = useState<string | null>(
    null,
  );
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ItemDraft | null>(null);
  const [baselineDraft, setBaselineDraft] = useState<ItemDraft | null>(null);
  const [validation, setValidation] = useState<string | null>(null);
  const [commandState, setCommandState] = useState<CommandState>({
    kind: "idle",
  });
  const [reviewCommand, setReviewCommand] = useState<RetryableCommand | null>(
    null,
  );
  const commandController = useRef<AbortController | null>(null);
  const retryCommand = useRef<RetryableCommand | null>(null);
  const editorFocus = useRef<HTMLElement | null>(null);

  const acceptWorkspace = useCallback((workspace: ReadinessWorkspace): void => {
    setResource({ kind: "loaded", value: workspace });
    const revision = workspace.currentRevision;
    setSelectedRevisionId(revision?.globalId ?? null);
    const firstBlocker = revision?.evaluation.blockers[0];
    const firstItem = firstBlocker
      ? revision.items.find(
          (item) => item.globalId === firstBlocker.itemGlobalId,
        )
      : revision?.items[0];
    setSelectedItemId(firstItem?.globalId ?? null);
    setSelectedCategoryKey(null);
    const nextDraft = firstItem
      ? itemDraft(firstItem, workspace.sourceOptions)
      : null;
    setDraft(nextDraft);
    setBaselineDraft(nextDraft);
    setValidation(null);
  }, []);

  useEffect(() => {
    commandController.current?.abort();
    const controller = new AbortController();
    void dataSource
      .loadWorkspace(projectId, controller.signal)
      .then((workspace) => {
        if (!controller.signal.aborted) acceptWorkspace(workspace);
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ReadinessRequestCancelledError
        )
          return;
        setResource({
          kind: "failed",
          failure: toRequestFailure(error),
          projectId,
        });
      });
    return () => {
      controller.abort();
    };
  }, [acceptWorkspace, attempt, dataSource, projectId]);

  useEffect(
    () => () => {
      commandController.current?.abort();
    },
    [],
  );

  const workspace = resource.kind === "loaded" ? resource.value : null;
  const currentRevision = workspace?.currentRevision ?? null;
  const selectedRevision =
    workspace?.revisions.find(
      (revision) => revision.globalId === selectedRevisionId,
    ) ?? currentRevision;
  const selectedItem =
    selectedRevision?.items.find((item) => item.globalId === selectedItemId) ??
    null;
  const historical = Boolean(
    selectedRevision &&
    currentRevision &&
    selectedRevision.globalId !== currentRevision.globalId,
  );
  const readOnly = workspace ? !workspace.permissions.canRevise : true;
  const availableProjectMembers = exactProjectMembers(members, projectId);

  const dirty = !historical && !readOnly && !sameDraft(draft, baselineDraft);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!dirty || !selectedRevision || !selectedItem) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: `${selectedRevision.instanceGlobalId}:${selectedItem.globalId}`,
      returnFocusTarget: () =>
        editorFocus.current ??
        document.getElementById(
          `readiness-item-${selectedItem.definition.key}`,
        ),
      version: `readiness-v${String(selectedRevision.instanceVersion)}`,
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [dirty, reportWorkspaceDirty, selectedItem, selectedRevision]);

  const reload = useCallback((): void => {
    commandController.current?.abort();
    retryCommand.current = null;
    setCommandState({ kind: "idle" });
    setReviewCommand(null);
    setResource({ kind: "loading" });
    setAttempt((value) => value + 1);
  }, []);

  const execute = useCallback(
    (operation: RetryableCommand): void => {
      if (!sessionCommandContext) return;
      commandController.current?.abort();
      const controller = new AbortController();
      commandController.current = controller;
      setCommandState({ kind: "processing" });
      void dataSource
        .reviseItem(projectId, operation.instanceId, operation.command, {
          csrfToken: sessionCommandContext.csrfToken,
          idempotencyKey: operation.idempotencyKey,
          signal: controller.signal,
        })
        .then((result) => {
          if (controller.signal.aborted) return;
          acceptWorkspace(result.workspace);
          setCommandState({ kind: "succeeded", replayed: result.replayed });
          retryCommand.current = null;
          reportWorkspaceDirty?.(null);
        })
        .catch((error: unknown) => {
          if (
            controller.signal.aborted ||
            error instanceof ReadinessRequestCancelledError
          )
            return;
          setCommandState({ kind: "failed", failure: toRequestFailure(error) });
        });
    },
    [
      acceptWorkspace,
      dataSource,
      projectId,
      reportWorkspaceDirty,
      sessionCommandContext,
    ],
  );

  const save = useCallback((): void => {
    if (
      !workspace ||
      !currentRevision ||
      !selectedItem ||
      !draft ||
      historical ||
      readOnly ||
      !sessionCommandContext
    )
      return;
    if (sameDraft(draft, baselineDraft)) {
      setValidation(t("Change at least one readiness item field."));
      return;
    }
    if (!draft.ownerMemberGlobalId) {
      setValidation(t("Select an exact Project member."));
      return;
    }
    if (
      !availableProjectMembers.some(
        (member) => member.globalId === draft.ownerMemberGlobalId,
      )
    ) {
      setValidation(t("Select an exact Project member."));
      return;
    }
    if (!draft.dueDate) {
      setValidation(t("Enter a due date."));
      return;
    }
    if (
      selectedItem.definition.completionRule === "confirmation" &&
      draft.state === "complete" &&
      !draft.confirmationValue.trim()
    ) {
      setValidation(t("Enter the controlled confirmation before completion."));
      return;
    }
    const command: ReviseProjectReadinessItemCommand = {
      confirmationValue: draft.confirmationValue.trim() || null,
      dueDate: draft.dueDate,
      expectedInstanceVersion: currentRevision.instanceVersion,
      expectedRevisionGlobalId: currentRevision.globalId,
      expectedRevisionSnapshotHash: currentRevision.snapshotHash,
      itemKey: selectedItem.definition.key,
      ownerMemberGlobalId: draft.ownerMemberGlobalId,
      sources: commandSources(selectedItem, draft, workspace.sourceOptions),
      state: draft.state,
    };
    const operation: RetryableCommand = {
      command,
      idempotencyKey: `readiness-revise-${globalThis.crypto.randomUUID()}`,
      instanceId: currentRevision.instanceGlobalId,
    };
    retryCommand.current = operation;
    setValidation(null);
    setReviewCommand(operation);
  }, [
    currentRevision,
    baselineDraft,
    draft,
    historical,
    readOnly,
    selectedItem,
    sessionCommandContext,
    t,
    availableProjectMembers,
    workspace,
  ]);

  const selectWithinWorkspace = useCallback(
    (perform: () => void, returnFocusTarget: HTMLElement): void => {
      if (requestWorkspaceTransition) {
        requestWorkspaceTransition(perform, returnFocusTarget);
        return;
      }
      perform();
    },
    [requestWorkspaceTransition],
  );

  const retry = useCallback((): void => {
    if (retryCommand.current) execute(retryCommand.current);
  }, [execute]);

  if (
    resource.kind === "loading" ||
    (resource.kind === "loaded" &&
      resource.value.projectGlobalId !== projectId) ||
    (resource.kind === "failed" && resource.projectId !== projectId)
  )
    return <LoadingState />;
  if (resource.kind === "failed")
    return <FailureState failure={resource.failure} onRetry={reload} />;
  if (!resource.value.currentRevision)
    return (
      <EmptyState
        dataSource={dataSource}
        members={availableProjectMembers}
        onInitialized={(nextWorkspace, replayed) => {
          acceptWorkspace(nextWorkspace);
          setCommandState({ kind: "succeeded", replayed });
        }}
        projectId={projectId}
        reportWorkspaceDirty={reportWorkspaceDirty}
        workspace={resource.value}
      />
    );

  const revision = selectedRevision ?? resource.value.currentRevision;
  const blockers = revision.evaluation.blockers;
  const visibleItems = selectedCategoryKey
    ? revision.items.filter(
        (item) => item.definition.categoryKey === selectedCategoryKey,
      )
    : revision.items;
  const blockerItemIds = new Set(
    blockers.map((blocker) => blocker.itemGlobalId),
  );

  return (
    <section
      aria-label={t("NPI readiness")}
      className="readiness-workspace"
      data-testid="readiness-workspace"
    >
      {!resource.value.permissions.canRevise ? (
        <section className="readiness-workspace__notice" role="status">
          <SemanticStatus label={t("Read-only workspace")} tone="warning" />
          <p>
            {t(
              "You can inspect exact retained readiness history but cannot revise it.",
            )}
          </p>
        </section>
      ) : !sessionCommandContext ? (
        <section className="readiness-workspace__notice" role="status">
          <SemanticStatus
            label={t("Session verification required")}
            tone="warning"
          />
          <p>{t("Reload the session before revising readiness items.")}</p>
        </section>
      ) : null}

      <Panel
        className="readiness-workspace__summary"
        title={t("Readiness blockers and score")}
      >
        <div data-testid="readiness-summary">
          <div data-testid="readiness-blocker-summary">
            <SemanticStatus
              label={
                blockers.length
                  ? t("{{count}} active blockers", { count: blockers.length })
                  : t("No active blockers")
              }
              tone={blockers.length ? "danger" : "success"}
            />
            {blockers.length ? (
              <ol className="readiness-workspace__blockers">
                {blockers.map((blocker) => {
                  const item = revision.items.find(
                    (candidate) => candidate.globalId === blocker.itemGlobalId,
                  );
                  return (
                    <li key={`${blocker.code}:${blocker.itemGlobalId}`}>
                      <strong>{blockerLabel(t, blocker.code)}</strong>{" "}
                      <span data-language-exempt="business-data">
                        {item?.definition.title ?? blocker.itemKey}
                      </span>{" "}
                      <code data-language-exempt="identifier">
                        {blocker.gate.gateKey}
                      </code>
                    </li>
                  );
                })}
              </ol>
            ) : null}
          </div>
          <div data-testid="readiness-score-summary">
            <DefinitionList
              rows={[
                {
                  label: t("Readiness state"),
                  value: revision.evaluation.ready
                    ? t("Ready")
                    : t("Not ready"),
                },
                {
                  label: t("Total score"),
                  value: scoreValue(
                    locale,
                    t,
                    revision.evaluation.totalScore.basisPoints,
                  ),
                },
                {
                  label: t("Earned weight"),
                  value: formatNumber(
                    locale,
                    revision.evaluation.totalScore.earnedWeight,
                  ),
                },
                {
                  label: t("Applicable weight"),
                  value: formatNumber(
                    locale,
                    revision.evaluation.totalScore.applicableWeight,
                  ),
                },
                {
                  label: t("Formula"),
                  value: revision.evaluation.formulaVersion,
                  exempt: "identifier",
                },
                {
                  label: t("Exact revision"),
                  value: t("Revision {{version}}", {
                    version: revision.instanceVersion,
                  }),
                },
              ]}
            />
            <table className="engineering-table engineering-table--compact">
              <thead>
                <tr>
                  <th scope="col">{t("Category")}</th>
                  <th scope="col">{t("Score")}</th>
                  <th scope="col">{t("Earned weight")}</th>
                  <th scope="col">{t("Applicable weight")}</th>
                </tr>
              </thead>
              <tbody>
                {revision.categories.map((category) => {
                  const score = revision.evaluation.categoryScores.find(
                    (candidate) => candidate.categoryKey === category.key,
                  );
                  return (
                    <tr key={category.key}>
                      <th data-language-exempt="business-data" scope="row">
                        {category.title}
                      </th>
                      <td>
                        {score
                          ? scoreValue(locale, t, score.basisPoints)
                          : t("Not available")}
                      </td>
                      <td>
                        {score
                          ? formatNumber(locale, score.earnedWeight)
                          : t("Not available")}
                      </td>
                      <td>
                        {score
                          ? formatNumber(locale, score.applicableWeight)
                          : t("Not available")}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </Panel>

      <div className="readiness-workspace__grid">
        <Panel
          className="readiness-workspace__categories"
          title={t("Categories")}
        >
          <nav aria-label={t("Readiness categories")}>
            <Button
              aria-current={selectedCategoryKey === null ? "page" : undefined}
              onClick={() => {
                setSelectedCategoryKey(null);
              }}
              visual="ghost"
            >
              {t("All categories")}
            </Button>
            {revision.categories.map((category) => (
              <Button
                aria-current={
                  selectedCategoryKey === category.key ? "page" : undefined
                }
                data-testid={`readiness-category-${category.key}`}
                key={category.key}
                onClick={(event) => {
                  if (selectedCategoryKey === category.key) return;
                  const returnFocusTarget = event.currentTarget;
                  selectWithinWorkspace(() => {
                    setSelectedCategoryKey(category.key);
                    const first = revision.items.find(
                      (item) => item.definition.categoryKey === category.key,
                    );
                    setSelectedItemId(first?.globalId ?? null);
                    const nextDraft = first
                      ? itemDraft(first, resource.value.sourceOptions)
                      : null;
                    setDraft(nextDraft);
                    setBaselineDraft(nextDraft);
                    setValidation(null);
                  }, returnFocusTarget);
                }}
                visual="ghost"
              >
                <span data-language-exempt="business-data">
                  {category.title}
                </span>
              </Button>
            ))}
          </nav>
        </Panel>

        <Panel
          bodyClassName="readiness-workspace__items-body"
          className="readiness-workspace__items"
          scrollableBody
          title={t("Readiness items")}
        >
          <table className="engineering-table engineering-table--compact">
            <thead>
              <tr>
                <th scope="col">{t("Item")}</th>
                <th scope="col">{t("Status")}</th>
                <th scope="col">{t("Owner")}</th>
                <th scope="col">{t("Due date")}</th>
                <th scope="col">{t("Evidence")}</th>
                <th scope="col">{t("Blocker")}</th>
                <th scope="col">{t("Gate")}</th>
              </tr>
            </thead>
            <tbody>
              {visibleItems.map((item) => (
                <tr
                  aria-selected={selectedItem?.globalId === item.globalId}
                  className={
                    selectedItem?.globalId === item.globalId
                      ? "engineering-table__row--selected"
                      : undefined
                  }
                  key={item.globalId}
                >
                  <th scope="row">
                    <button
                      aria-label={t("Inspect readiness item {{item}}", {
                        item: item.definition.title,
                      })}
                      className="readiness-workspace__item-select"
                      data-language-exempt-tokens={JSON.stringify([
                        item.definition.title,
                      ])}
                      data-testid={`readiness-item-${item.definition.key}`}
                      id={`readiness-item-${item.definition.key}`}
                      onClick={(event) => {
                        if (selectedItem?.globalId === item.globalId) return;
                        editorFocus.current = event.currentTarget;
                        const returnFocusTarget = event.currentTarget;
                        selectWithinWorkspace(() => {
                          setSelectedItemId(item.globalId);
                          const nextDraft = itemDraft(
                            item,
                            resource.value.sourceOptions,
                          );
                          setDraft(nextDraft);
                          setBaselineDraft(nextDraft);
                          setValidation(null);
                        }, returnFocusTarget);
                      }}
                      type="button"
                    >
                      <span data-language-exempt="business-data">
                        {item.definition.title}
                      </span>
                    </button>
                  </th>
                  <td>
                    <SemanticStatus
                      label={itemStateLabel(t, item.state)}
                      tone={itemStateTone(item.state)}
                    />
                  </td>
                  <td
                    data-language-exempt={
                      item.owner ? "business-data" : undefined
                    }
                  >
                    {item.owner?.userId ?? t("Unassigned")}
                  </td>
                  <td>
                    {item.dueDate
                      ? formatDate(locale, item.dueDate)
                      : t("Not available")}
                  </td>
                  <td>{formatNumber(locale, item.sources.length)}</td>
                  <td>
                    {blockerItemIds.has(item.globalId) ? (
                      <SemanticStatus label={t("Blocked")} tone="danger" />
                    ) : (
                      <SemanticStatus
                        label={t("No active blocker")}
                        tone="neutral"
                      />
                    )}
                  </td>
                  <td>
                    <code data-language-exempt="identifier">
                      {item.gate.gateKey}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <ItemInspector
          commandState={commandState}
          draft={draft}
          draftChanged={dirty}
          historical={historical}
          item={selectedItem}
          members={availableProjectMembers}
          onDraftChange={(next) => {
            setDraft(next);
            setValidation(null);
          }}
          onReload={reload}
          onRetryCommand={retry}
          onSave={save}
          readOnly={readOnly}
          sourceOptions={resource.value.sourceOptions}
          validation={validation}
        />
      </div>

      <Panel
        className="readiness-workspace__history"
        title={t("Readiness history")}
      >
        <div data-testid="readiness-history">
          <table className="engineering-table engineering-table--compact">
            <thead>
              <tr>
                <th scope="col">{t("Revision")}</th>
                <th scope="col">{t("Created at")}</th>
                <th scope="col">{t("Created by")}</th>
                <th scope="col">{t("Score")}</th>
                <th scope="col">{t("Active blockers")}</th>
                <th scope="col">{t("Readiness state")}</th>
              </tr>
            </thead>
            <tbody>
              {[...resource.value.revisions]
                .reverse()
                .map((historyRevision) => (
                  <tr key={historyRevision.globalId}>
                    <th scope="row">
                      <Button
                        aria-current={
                          revision.globalId === historyRevision.globalId
                            ? "page"
                            : undefined
                        }
                        data-testid={`readiness-revision-${String(historyRevision.instanceVersion)}`}
                        onClick={(event) => {
                          if (revision.globalId === historyRevision.globalId)
                            return;
                          const returnFocusTarget = event.currentTarget;
                          selectWithinWorkspace(() => {
                            setSelectedRevisionId(historyRevision.globalId);
                            const blocker =
                              historyRevision.evaluation.blockers[0];
                            const item = blocker
                              ? historyRevision.items.find(
                                  (candidate) =>
                                    candidate.globalId === blocker.itemGlobalId,
                                )
                              : historyRevision.items[0];
                            setSelectedItemId(item?.globalId ?? null);
                            setSelectedCategoryKey(null);
                            const nextDraft = item
                              ? itemDraft(item, resource.value.sourceOptions)
                              : null;
                            setDraft(nextDraft);
                            setBaselineDraft(nextDraft);
                            setValidation(null);
                            setCommandState({ kind: "idle" });
                          }, returnFocusTarget);
                        }}
                        visual="ghost"
                      >
                        {t("Revision {{version}}", {
                          version: historyRevision.instanceVersion,
                        })}
                      </Button>
                    </th>
                    <td>{formatDateTime(locale, historyRevision.createdAt)}</td>
                    <td data-language-exempt="business-data">
                      {historyRevision.createdByUserId}
                    </td>
                    <td>
                      {scoreValue(
                        locale,
                        t,
                        historyRevision.evaluation.totalScore.basisPoints,
                      )}
                    </td>
                    <td>
                      {formatNumber(
                        locale,
                        historyRevision.evaluation.blockers.length,
                      )}
                    </td>
                    <td>
                      {historyRevision.evaluation.ready
                        ? t("Ready")
                        : t("Not ready")}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <UnavailableProjectionPanel workspace={resource.value} />
      <FormalQualityLinkInspector
        dataSource={formalQualityDataSource}
        projectId={projectId}
        source={{
          scopeGlobalId: resource.value.currentRevision.instanceGlobalId,
          scopeKind: "readiness",
          sourceCapability: resource.value.permissions.canRevise,
          sourceGlobalId: resource.value.currentRevision.instanceGlobalId,
          sourceKind: "readiness_assessment",
          sourceSnapshotHash: resource.value.currentRevision.snapshotHash,
          sourceVersion: resource.value.currentRevision.instanceVersion,
        }}
      />
      {reviewCommand && selectedItem && currentRevision ? (
        <ImpactReview
          confirmLabel={t("Append readiness revision")}
          contextRows={[
            {
              exempt: "business-data",
              label: t("Readiness item"),
              value: selectedItem.definition.title,
            },
            {
              exempt: "identifier",
              label: t("Gate"),
              value: selectedItem.gate.gateKey,
            },
            {
              label: t("Current state"),
              value: itemStateLabel(t, selectedItem.state),
            },
            {
              label: t("Proposed state"),
              value: itemStateLabel(t, reviewCommand.command.state),
            },
          ]}
          details={{
            audit: t(
              "The successor revision, receipt, actor and exact source references are audited atomically.",
            ),
            failureHandling: t(
              "A failure creates no partial successor. Retry uses the same command identity.",
            ),
            impact: t(
              "Appends one immutable successor and lets the server derive scores and blockers again.",
            ),
            irreversible: t(
              "The retained revision cannot be overwritten; corrections require another successor.",
            ),
            objectIdentity: selectedItem.definition.key,
            permission: t(
              "An enabled internal System Manager with exact Project access is required.",
            ),
            version: t("Revision {{version}}", {
              version: currentRevision.instanceVersion,
            }),
          }}
          onCancel={() => {
            setReviewCommand(null);
          }}
          onConfirm={() => {
            setReviewCommand(null);
            execute(reviewCommand);
          }}
          reasonRequired={false}
          returnFocusTarget={() => editorFocus.current}
          title={t("Review readiness revision")}
        />
      ) : null}
    </section>
  );
}
