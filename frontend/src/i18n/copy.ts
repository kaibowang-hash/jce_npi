import type {
  ActionCode,
  ActivityEvent,
  AssignmentCode,
  DomainWorkItemKind,
  DomainWorkItemSeverity,
  ExecutionRow,
  GateStep,
  LifecycleStep,
  ProjectResponsibility,
  ProjectResponsibilityContext,
  Scenario,
  SourceSystem,
  SyncState,
  WorkKind,
  WorkTitleCode,
} from "../domain/view-models";
import {
  isProjectPolicyLabelSource,
  type ProjectPolicyLabelSource,
} from "../generated/project-policy-label-sources";
import type { TranslationValues } from "./runtime";

export type Translator = (
  source: string,
  values?: TranslationValues,
  context?: string,
) => string;

export function workKindLabel(t: Translator, code: WorkKind): string {
  switch (code) {
    case "approval":
      return t("Approval");
    case "blocker":
      return t("Blocker");
    case "action":
      return t("Action item");
    case "integration":
      return t("Integration");
    case "task":
      return t("Task");
    case "decision":
      return t("Decision");
  }
}

export function workTitleLabel(t: Translator, code: WorkTitleCode): string {
  switch (code) {
    case "g5_sample_approval":
      return t("Review G5 sample approval");
    case "t1_flash_open":
      return t("Close the major T1 flash defect");
    case "hot_runner_drawing":
      return t("Confirm the hot runner interface drawing");
    case "tool_asset_failed":
      return t("Tool asset creation failed");
    case "intake_photos":
      return t("Upload customer-owned tool intake photos");
    case "dimension_deviation":
      return t("Review the temporary dimensional deviation");
  }
}

export function assignmentLabel(t: Translator, code: AssignmentCode): string {
  switch (code) {
    case "engineering_signatory":
      return t("You are the engineering signatory.");
    case "g5_blocker_owner":
      return t("This blocks G5 and you own the corrective action.");
    case "supplier_waiting":
      return t("The supplier is waiting for your decision.");
    case "erp_validation_failed":
      return t("ERPNext validation failed and requires your review.");
    case "template_assignment":
      return t("The project template assigned this task to you.");
    case "quality_requested":
      return t("Quality requested an engineering decision.");
  }
}

export function actionLabel(t: Translator, code: ActionCode): string {
  switch (code) {
    case "open_review":
      return t("Open review");
    case "resolve_defect":
      return t("Resolve defect");
    case "view_context":
      return t("View context");
    case "view_execution":
      return t("View execution");
    case "start":
      return t("Start");
    case "review_impact":
      return t("Review impact");
  }
}

export function syncStateLabel(
  t: Translator,
  code:
    | SyncState
    | "pending_approval"
    | "blocked"
    | "not_started"
    | "queued"
    | "cancelled"
    | "succeeded",
): string {
  switch (code) {
    case "local":
      return t("Saved in NPI One");
    case "pending":
      return t("Pending");
    case "pending_approval":
      return t("Pending approval");
    case "processing":
      return t("Processing");
    case "synced":
      return t("Synchronized");
    case "partial":
      return t("Partially succeeded");
    case "failed_retryable":
      return t("Failed, retry available");
    case "failed_final":
      return t("Failed, manual action required");
    case "stale":
      return t("Stale");
    case "conflict":
      return t("Version conflict");
    case "blocked":
      return t("Blocked");
    case "not_started":
      return t("Not started");
    case "queued":
      return t("Queued");
    case "cancelled":
      return t("Cancelled");
    case "succeeded":
      return t("Completed in ERPNext");
  }
}

export function sourceSystemLabel(t: Translator, source: SourceSystem): string {
  switch (source) {
    case "NPI_ONE":
      return t("NPI One");
    case "ERPNEXT":
      return t("ERPNext");
    case "COMPUTED":
      return t("Computed");
  }
}

export function projectResponsibilityLabel(
  t: Translator,
  responsibility: ProjectResponsibility,
): string {
  switch (responsibility) {
    case "responsible":
      return t("Responsible");
    case "accountable":
      return t("Accountable");
    case "consulted":
      return t("Consulted");
    case "informed":
      return t("Informed");
  }
}

export function projectResponsibilityContextLabel(
  t: Translator,
  context: ProjectResponsibilityContext,
): string {
  switch (context) {
    case "project":
      return t("Project");
    case "wbs_item":
      return t("WBS item");
    case "domain_work_item":
      return t("Domain work item");
  }
}

function knownPolicyLabel(
  t: Translator,
  labelSource: ProjectPolicyLabelSource,
): string {
  switch (labelSource) {
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

/**
 * Translates only finite policy label sources from the canonical registry.
 * The literal switch is exhaustive against its generated union so catalog
 * extraction and registry drift stay compile-time visible. Untrusted values
 * never reach the translator.
 */
export function governedPolicyLabel(
  t: Translator,
  labelSource: unknown,
): string {
  return isProjectPolicyLabelSource(labelSource)
    ? knownPolicyLabel(t, labelSource)
    : t("Policy label unavailable");
}

export function domainWorkItemKindLabel(
  t: Translator,
  kind: DomainWorkItemKind,
): string {
  switch (kind) {
    case "risk":
      return t("Risk");
    case "issue":
      return t("Issue");
    case "action":
      return t("Action item");
    case "decision_request":
      return t("Decision request");
  }
}

export function domainWorkItemSeverityLabel(
  t: Translator,
  severity: DomainWorkItemSeverity,
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

export function gateLabel(t: Translator, step: GateStep): string {
  switch (step.labelCode) {
    case "feasibility":
      return t("Feasibility");
    case "initiation":
      return t("Initiation");
    case "design_freeze":
      return t("Design freeze");
    case "tooling_start":
      return t("Tooling start");
    case "trial_iteration":
      return t("Trial iteration");
    case "sample_approval":
      return t("Sample approval");
    case "npi_ready":
      return t("NPI readiness");
    case "sop_handover":
      return t("SOP handover");
  }
}

export function lifecycleLabel(t: Translator, step: LifecycleStep): string {
  switch (step.code) {
    case "requirement":
      return t("Requirement");
    case "design":
      return t("Design");
    case "manufacturing":
      return t("Manufacturing");
    case "t0":
      return t("T0");
    case "t1":
      return t("T1");
    case "acceptance":
      return t("Acceptance");
    case "erp_asset":
      return t("ERPNext asset");
  }
}

export function activityLabel(t: Translator, event: ActivityEvent): string {
  switch (event.summaryCode) {
    case "revision_released":
      return t("Released tooling design revision C.");
    case "defect_assigned":
      return t("Assigned the major flash defect for correction.");
    case "quality_failed":
      return t("Formal quality result changed to failed.");
    case "execution_retry":
      return t("Queued a safe retry for the execution request.");
    case "comment_added":
      return t("Added a controlled engineering comment.");
    case "gate_approved":
      return t("Approved the Gate decision snapshot.");
  }
}

export function operationLabel(
  t: Translator,
  code: ExecutionRow["operationCode"],
): string {
  switch (code) {
    case "tool_asset":
      return t("Create tool asset");
    case "item_release":
      return t("Release formal item");
    case "mbom_update":
      return t("Update manufacturing BOM");
    case "quality_request":
      return t("Request quality inspection");
    case "file_reference":
      return t("Publish controlled file reference");
    case "purchase_request":
      return t("Create purchase request");
  }
}

export function scenarioLabel(t: Translator, scenario: Scenario): string {
  switch (scenario) {
    case "normal":
      return t("Normal");
    case "loading":
      return t("Loading");
    case "empty":
      return t("Empty");
    case "no_permission":
      return t("No permission");
    case "read_only":
      return t("Read only");
    case "partial":
      return t("Partial data");
    case "error":
      return t("Error");
    case "conflict":
      return t("Conflict");
    case "validation":
      return t("Validation error");
    case "queued":
      return t("Queued operation");
    case "processing":
      return t("Processing operation");
    case "failed_retryable":
      return t("Retryable failure");
    case "failed_final":
      return t("Final failure");
    case "dirty":
      return t("Unsaved changes");
  }
}
