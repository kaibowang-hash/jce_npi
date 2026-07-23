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
