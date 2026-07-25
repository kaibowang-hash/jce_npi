import type { ProjectPolicyLabelSource } from "../generated/project-policy-label-sources";

export type { ProjectPolicyLabelSource } from "../generated/project-policy-label-sources";

export type ScreenId =
  | "work"
  | "project"
  | "gate"
  | "tooling"
  | "trial"
  | "execution";

export type Scenario =
  | "normal"
  | "loading"
  | "empty"
  | "no_permission"
  | "read_only"
  | "partial"
  | "error"
  | "conflict"
  | "validation"
  | "queued"
  | "processing"
  | "failed_retryable"
  | "failed_final"
  | "dirty";

export type SemanticTone =
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "danger";
export type SourceSystem = "NPI_ONE" | "ERPNEXT" | "COMPUTED";
export type SyncState =
  | "local"
  | "pending"
  | "processing"
  | "synced"
  | "partial"
  | "failed_retryable"
  | "failed_final"
  | "stale"
  | "conflict";

export interface SourceStatus {
  sourceSystem: SourceSystem;
  editableIn: "NPI_ONE" | "ERPNEXT" | "NONE";
  syncState: SyncState;
  lastSyncedAt?: string;
  externalReference?: string;
}

export type WorkKind =
  | "approval"
  | "blocker"
  | "action"
  | "integration"
  | "task"
  | "decision";
export type WorkTitleCode =
  | "g5_sample_approval"
  | "t1_flash_open"
  | "hot_runner_drawing"
  | "tool_asset_failed"
  | "intake_photos"
  | "dimension_deviation";
export type AssignmentCode =
  | "engineering_signatory"
  | "g5_blocker_owner"
  | "supplier_waiting"
  | "erp_validation_failed"
  | "template_assignment"
  | "quality_requested";
export type ActionCode =
  | "open_review"
  | "resolve_defect"
  | "view_context"
  | "view_execution"
  | "start"
  | "review_impact";

export interface WorkItemViewModel {
  id: string;
  kind: WorkKind;
  titleCode: WorkTitleCode;
  assignmentCode: AssignmentCode;
  contextCode: string;
  contextName: string;
  dueAt: string;
  status: SyncState | "pending_approval" | "blocked" | "not_started";
  actionCode: ActionCode;
  targetPath: string;
  blocking: boolean;
  source: SourceStatus;
}

export interface GateStep {
  code: string;
  labelCode:
    | "feasibility"
    | "initiation"
    | "design_freeze"
    | "tooling_start"
    | "trial_iteration"
    | "sample_approval"
    | "npi_ready"
    | "sop_handover";
  state: "completed" | "current" | "blocked" | "upcoming";
}

export type ProjectType = "customer_owned_tool" | "new_tool" | "tool_change";

export type ProjectReferenceType =
  | "customer"
  | "product"
  | "part"
  | "tooling"
  | "order";

export interface ProjectReferenceViewModel {
  type: ProjectReferenceType;
  sourceSystem: "NPI_ONE" | "ERPNEXT";
  sourceObjectId: string;
  globalId?: string;
}

export interface ProjectGateShellViewModel {
  globalId: string;
  key: string;
  title: string;
  sequence: number;
  state: "not_started";
  version: number;
}

export interface ProjectCockpitViewModel {
  project: {
    globalId: string;
    businessCode: string;
    title: string;
    projectType: ProjectType;
    state: "draft";
    version: number;
    tenantId: string;
    ownerUserId: string;
    targetSop: string;
    createdAt: string;
    lastChangedAt: string;
    lastChangedBy: string;
    source: {
      sourceSystem: "NPI_ONE";
      editableIn: "NPI_ONE";
      syncState: "local";
    };
  };
  templateRef: {
    globalId: string;
    code: string;
    version: number;
    snapshotHash: string;
  };
  references: readonly ProjectReferenceViewModel[];
  gates: readonly ProjectGateShellViewModel[];
  permissions: {
    canView: true;
    canContribute: boolean;
    canAdminister: boolean;
  };
}

export type GateRequirementClassification = "required" | "optional";
export type GateRequirementPriority = "P0" | "P1" | "P2";
export type GateEvidenceKind = "wbs_item" | "file_revision";
export type GateEvidenceScanState = "pending" | "clean" | "failed" | "infected";
export type GateRequirementEvidenceState =
  | "missing"
  | "attached"
  | "scan_pending"
  | "scan_clean"
  | "scan_failed"
  | "scan_infected";

export interface GateEvidencePersonViewModel {
  memberId: string;
  userId: string;
  displayName: string;
}

export interface GateEvidenceReferenceViewModel {
  globalId: string;
  kind: GateEvidenceKind;
  sourceObjectType: GateEvidenceKind;
  sourceGlobalId: string;
  revision: number;
  objectHash: string;
  createdAt: string;
  createdBy: string;
  file?: {
    fileName: string;
    mimeType: string;
    sizeBytes: number;
    scanState: GateEvidenceScanState;
  };
}

export interface GateRequirementViewModel {
  globalId: string;
  key: string;
  title: string;
  classification: GateRequirementClassification;
  priority: GateRequirementPriority;
  owner: GateEvidencePersonViewModel;
  reviewers: readonly GateEvidencePersonViewModel[];
  dueDate: string;
  allowedEvidenceKinds: readonly GateEvidenceKind[];
  evidenceState: GateRequirementEvidenceState;
  evidence: readonly GateEvidenceReferenceViewModel[];
}

export interface GateEvidenceViewModel {
  project: {
    globalId: string;
    businessCode: string;
    title: string;
  };
  gate: {
    globalId: string;
    key: string;
    title: string;
    state: "not_started";
    version: number;
    dueDate: string;
    templateRef: {
      globalId: string;
      version: number;
      snapshotHash: string;
    };
    requirementSnapshotHash: string;
    frozenAt: string;
    frozenBy: string;
  };
  requirements: readonly GateRequirementViewModel[];
  summary: {
    requiredCount: number;
    missingRequiredCount: number;
    unsafeScanCount: number;
    evidenceCount: number;
  };
  permissions: {
    canView: true;
    canAttachEvidence: boolean;
    canAdminister: boolean;
  };
}

export type GateReviewState =
  | "not_started"
  | "in_review"
  | "decided"
  | "requires_review";
export type GateReviewOutcome = "approved" | "rejected";
export type GateDecisionOutcome = "pass" | "conditional_pass" | "reject";
export type GateReviewCycleTrigger =
  | "manual_start"
  | "manual_reopen"
  | "dependency_change";
export type GateReviewCycleState =
  | "active"
  | "decided"
  | "invalidated"
  | "superseded";
export type GateReviewStepState =
  | "waiting"
  | "available"
  | "approved"
  | "rejected";
export type GateReviewExceptionState = "pending" | "approved" | "rejected";
export type GateReviewExceptionDecisionOutcome = "approved" | "rejected";
export type GateReviewAuthorityPurpose =
  | "review"
  | "decision"
  | "reopen"
  | "exception";

export interface GateReviewPolicyReferenceViewModel {
  globalId: string;
  version: number;
  snapshotHash: string;
}

export interface GateReviewMemberViewModel {
  memberGlobalId: string;
  userId: string;
  displayName: string;
}

export interface GateReviewAuthoritySlotViewModel {
  slot: string;
  purpose: GateReviewAuthorityPurpose;
}

export interface GateReviewExceptionRuleViewModel {
  kind: string;
  eligibleRequirementKeys: readonly string[];
  approvalAuthoritySlot: string;
  maximumValidityDays: number;
  requiredClosureActionKind: "action";
}

export interface GateReviewAvailablePolicyViewModel {
  policyRef: GateReviewPolicyReferenceViewModel;
  authoritySlots: readonly GateReviewAuthoritySlotViewModel[];
  exceptionRules: readonly GateReviewExceptionRuleViewModel[];
}

export interface GateReviewAuthorityBindingViewModel {
  slot: string;
  memberGlobalId: string;
  userId: string;
  displayName: string;
}

export interface GateReviewRecordViewModel {
  globalId: string;
  stepKey: string;
  outcome: GateReviewOutcome;
  opinion: string;
  actor: string;
  reviewedAt: string;
  inputHash: string;
  snapshotHash: string;
}

export interface GateReviewSelectedStepViewModel {
  stepKey: string;
  sequence: number;
  slot: string;
  assignedMember: GateReviewMemberViewModel;
  state: GateReviewStepState;
  review: GateReviewRecordViewModel | null;
}

export interface GateReviewExceptionDecisionViewModel {
  outcome: GateReviewOutcome;
  approver: GateReviewMemberViewModel;
  opinion: string;
  decidedAt: string;
  snapshotHash: string;
}

export interface GateReviewExactObjectReferenceViewModel {
  globalId: string;
  version: number;
  snapshotHash: string;
}

export interface GateReviewClosureActionReferenceViewModel {
  globalId: string;
  version: number | null;
  snapshotHash: string | null;
}

export interface GateReviewExceptionViewModel {
  globalId: string;
  requirementGlobalId: string;
  requirementKey: string;
  kind: string;
  reason: string;
  risk: string;
  requester: GateReviewMemberViewModel;
  requestedAt: string;
  expiresAt: string;
  requestSchemaVersion: 1 | 2;
  closureActionRef: GateReviewClosureActionReferenceViewModel;
  state: GateReviewExceptionState;
  version: number;
  requestSnapshotHash: string;
  decision: GateReviewExceptionDecisionViewModel | null;
  allowedOutcomes: readonly GateReviewExceptionDecisionOutcome[];
}

export interface GateReviewExceptionRequestOptionViewModel {
  requirementGlobalId: string;
  requirementKey: string;
  kind: string;
  maximumValidityDays: number;
  closureActionGlobalIds: readonly string[];
}

export interface GateReviewDecisionBlockedReasonViewModel {
  outcome: GateDecisionOutcome;
  code: GateReviewDecisionBlockedReasonCode;
}

export type GateReviewDecisionBlockedReasonCode =
  | "REVIEW_CYCLE_CLOSED"
  | "GATE_INPUT_CHANGED"
  | "DECISION_AUTHORITY_REQUIRED"
  | "REVIEWS_INCOMPLETE"
  | "FILE_EVIDENCE_UNSAFE"
  | "GATE_BLOCKED"
  | "REQUIRED_P0_EVIDENCE_MISSING"
  | "REQUIRED_EVIDENCE_MISSING"
  | "EXCEPTION_NOT_REQUIRED"
  | "APPROVED_EXCEPTION_REQUIRED";

export interface GateReviewDecisionReadinessViewModel {
  allowedOutcomes: readonly GateDecisionOutcome[];
  blockedReasons: readonly GateReviewDecisionBlockedReasonViewModel[];
}

export interface GateReviewCycleViewModel {
  globalId: string;
  number: number;
  trigger: GateReviewCycleTrigger;
  state: GateReviewCycleState;
  version: number;
  policyRef: GateReviewPolicyReferenceViewModel;
  policyDefinition: GateReviewAvailablePolicyViewModel;
  inputHash: string;
  bindings: readonly GateReviewAuthorityBindingViewModel[];
  selectedSteps: readonly GateReviewSelectedStepViewModel[];
  exceptions: readonly GateReviewExceptionViewModel[];
  startedAt: string;
  startedBy: string;
}

export interface GateReviewInputRequirementViewModel {
  globalId: string;
  requirementKey: string;
  priority: GateRequirementPriority;
  sourceVersion: number;
  sourceHash: string;
  evidenceComplete: boolean;
}

export interface GateReviewInputEvidenceViewModel {
  globalId: string;
  requirementGlobalId: string;
  evidenceKind: GateEvidenceKind;
  sourceGlobalId: string;
  sourceVersion: number;
  sourceHash: string;
  isFile: boolean;
  fileSafe: boolean;
}

export interface GateReviewInputBlockerViewModel {
  globalId: string;
  version: number;
  state: string;
  blocking: boolean;
  terminal: boolean;
}

export interface GateReviewInputDependencyViewModel {
  kind: "gate_input_snapshot";
  globalId: string;
  version: number;
  snapshotHash: string;
}

export interface GateReviewInputSnapshotViewModel {
  schemaVersion: 1;
  gateGlobalId: string;
  projectGlobalId: string;
  tenantId: string;
  gateVersion: number;
  requirements: readonly GateReviewInputRequirementViewModel[];
  evidence: readonly GateReviewInputEvidenceViewModel[];
  blockers: readonly GateReviewInputBlockerViewModel[];
  dependencies: readonly GateReviewInputDependencyViewModel[];
}

export interface GateDecisionDetailViewModel {
  lineageHash: string;
  cycleNumber: number;
  policyRef: GateReviewPolicyReferenceViewModel;
  inputSnapshot: GateReviewInputSnapshotViewModel;
  reviewHashes: readonly string[];
  exceptionHashes: readonly string[];
  cycleVersion: number;
}

export interface GateDecisionSummaryViewModel {
  globalId: string;
  cycleGlobalId: string;
  outcome: GateDecisionOutcome;
  inputHash: string;
  snapshotHash: string;
  decidedAt: string;
  decidedBy: string;
  current: boolean;
  detail: GateDecisionDetailViewModel;
}

export interface GateReviewClosureActionViewModel {
  globalId: string;
  title: string;
  state: string;
  stateLabelSource: ProjectPolicyLabelSource;
  version: number;
}

export interface GateReviewBlockerViewModel {
  globalId: string;
  kind: DomainWorkItemKind;
  title: string;
  state: string;
  stateLabelSource: ProjectPolicyLabelSource;
  dueAt: string;
  owner: string;
}

export type GateReviewDependencyEventType = "invalidated" | "refreshed";

export interface GateReviewDependencyChangeViewModel {
  eventGlobalId: string;
  eventType: GateReviewDependencyEventType;
  priorCycleGlobalId: string;
  successorCycleGlobalId: string;
  impactActionGlobalId?: string | null;
  oldInputHash: string;
  newInputHash: string;
  priorDecisionGlobalId: string | null;
  priorDecisionLineageHash: string | null;
  actorUserId: string;
  initiatedByUserId: string | null;
  occurredAt: string;
  reason: string;
}

export interface GateReviewViewModel {
  project: GateEvidenceViewModel["project"];
  gate: {
    globalId: string;
    key: string;
    title: string;
    reviewState: GateReviewState;
    version: number;
    currentCycleGlobalId: string | null;
    latestDecisionGlobalId: string | null;
    latestDecisionHash: string | null;
    latestDecisionOutcome: GateDecisionOutcome | null;
    downstreamDecisionCurrent: boolean;
  };
  evidence: GateEvidenceViewModel;
  activeCycle: GateReviewCycleViewModel | null;
  decisions: readonly GateDecisionSummaryViewModel[];
  availablePolicies: readonly GateReviewAvailablePolicyViewModel[];
  eligibleMembers: readonly GateReviewMemberViewModel[];
  eligibleClosureActions: readonly GateReviewClosureActionViewModel[];
  exceptionRequestOptions: readonly GateReviewExceptionRequestOptionViewModel[];
  decisionReadiness: GateReviewDecisionReadinessViewModel;
  blockers: readonly GateReviewBlockerViewModel[];
  dependencyChanges: readonly GateReviewDependencyChangeViewModel[];
  permissions: {
    canView: true;
    canStartReview: boolean;
    canReview: boolean;
    canRequestException: boolean;
    canApproveException: boolean;
    canDecide: boolean;
    canReopen: boolean;
  };
}

export interface ProjectWorkPolicyReference {
  globalId: string;
  version: number;
  snapshotHash: string;
}

export interface ProjectMemberViewModel {
  globalId: string;
  projectId: string;
  userId: string;
  effectiveFrom: string;
  effectiveTo?: string;
  version: number;
}

export interface ProjectRoleAssignmentViewModel {
  globalId: string;
  projectId: string;
  memberId: string;
  roleKey: string;
  effectiveFrom: string;
  effectiveTo?: string;
  version: number;
}

export interface ProjectSubstitutionViewModel {
  globalId: string;
  projectId: string;
  roleAssignmentId: string;
  substituteMemberId: string;
  effectiveFrom: string;
  effectiveTo: string;
  version: number;
}

export type ProjectResponsibility =
  | "responsible"
  | "accountable"
  | "consulted"
  | "informed";

export type ProjectResponsibilityContext =
  | "project"
  | "wbs_item"
  | "domain_work_item";

export interface ProjectRaciAssignmentViewModel {
  globalId: string;
  projectId: string;
  contextType: ProjectResponsibilityContext;
  contextId: string;
  responsibilityKey: string;
  roleAssignmentId: string;
  raci: ProjectResponsibility;
  version: number;
}

export type ProjectWbsStateKey = string;

export interface ProjectWbsItemViewModel {
  globalId: string;
  projectId: string;
  code: string;
  title: string;
  parentId?: string;
  ownerRoleAssignmentId?: string;
  plannedStart: string;
  plannedFinish: string;
  actualStart?: string;
  actualFinish?: string;
  milestone: boolean;
  statusKey: ProjectWbsStateKey;
  statusLabelSource: ProjectPolicyLabelSource;
  progressPercent: number;
  critical: boolean;
  version: number;
}

export interface ProjectDependencyViewModel {
  globalId: string;
  projectId: string;
  predecessorItemId: string;
  successorItemId: string;
  version: number;
}

export interface ProjectPlanBaselineViewModel {
  globalId: string;
  projectId: string;
  projectVersion: number;
  workPolicyRef: ProjectWorkPolicyReference;
  label: string;
  snapshotHash: string;
  capturedAt: string;
  capturedBy: string;
  version: number;
}

export interface ProjectPlanBaselineComparisonItemViewModel {
  wbsItemId: string;
  baselinePlannedStart: string;
  baselinePlannedFinish: string;
  currentPlannedStart: string;
  currentPlannedFinish: string;
  startVarianceDays: number;
  finishVarianceDays: number;
  critical: boolean;
}

export interface ProjectPlanBaselineComparisonViewModel {
  baselineId: string;
  baselineProjectVersion: number;
  currentProjectVersion: number;
  items: readonly ProjectPlanBaselineComparisonItemViewModel[];
}

export interface ProjectWorkContextViewModel {
  projectId: string;
  projectVersion: number;
  initialized: boolean;
  workPolicyRef: ProjectWorkPolicyReference | null;
  members: readonly ProjectMemberViewModel[];
  roleAssignments: readonly ProjectRoleAssignmentViewModel[];
  substitutions: readonly ProjectSubstitutionViewModel[];
  raciAssignments: readonly ProjectRaciAssignmentViewModel[];
  wbsItems: readonly ProjectWbsItemViewModel[];
  dependencies: readonly ProjectDependencyViewModel[];
  baselines: readonly ProjectPlanBaselineViewModel[];
  baselineComparison: ProjectPlanBaselineComparisonViewModel | null;
  permissions: ProjectCockpitViewModel["permissions"];
}

export type DomainWorkItemKind =
  | "risk"
  | "issue"
  | "action"
  | "decision_request";
export type DomainWorkItemSeverity = "low" | "medium" | "high" | "critical";
export type DomainWorkItemStateKey = string;

export interface DomainWorkItemContextViewModel {
  projectId: string;
  stageId?: string;
  wbsItemId?: string;
}

export interface DomainWorkItemViewModel {
  globalId: string;
  projectId: string;
  kind: DomainWorkItemKind;
  title: string;
  detail?: string;
  context: DomainWorkItemContextViewModel;
  ownerUserId: string;
  dueAt: string;
  severity: DomainWorkItemSeverity;
  blocking: boolean;
  relatedWorkItemIds: readonly string[];
  workPolicyRef: ProjectWorkPolicyReference;
  stateKey: DomainWorkItemStateKey;
  stateLabelSource: ProjectPolicyLabelSource;
  overdue: boolean;
  version: number;
  createdAt: string;
  lastChangedAt: string;
  source: {
    sourceSystem: "NPI_ONE";
    editableIn: "NPI_ONE";
    syncState: "local";
  };
}

export interface DomainWorkItemPageViewModel {
  projectId: string;
  projectVersion: number;
  items: readonly DomainWorkItemViewModel[];
  nextCursor: string | null;
}

export interface LifecycleStep {
  code:
    | "requirement"
    | "design"
    | "manufacturing"
    | "t0"
    | "t1"
    | "acceptance"
    | "erp_asset";
  state: "completed" | "current" | "blocked" | "upcoming";
}

export interface ActivityEvent {
  id: string;
  kind: "comment" | "action" | "approval" | "version" | "integration";
  actor: string;
  occurredAt: string;
  reference: string;
  summaryCode:
    | "revision_released"
    | "defect_assigned"
    | "quality_failed"
    | "execution_retry"
    | "comment_added"
    | "gate_approved";
}

export interface ExecutionRow {
  id: string;
  operationCode:
    | "tool_asset"
    | "item_release"
    | "mbom_update"
    | "quality_request"
    | "file_reference"
    | "purchase_request";
  context: string;
  createdAt: string;
  state: SyncState | "queued" | "cancelled" | "succeeded";
  traceId: string;
}
