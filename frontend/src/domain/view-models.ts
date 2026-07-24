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
