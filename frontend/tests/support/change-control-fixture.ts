import type {
  EngineeringChangeCommandResult,
  EngineeringChangeContent,
  EngineeringChangeDetail,
  EngineeringChangeEvent,
  EngineeringChangeList,
  EngineeringChangeRevision,
  EngineeringChangeSummaryReceipt,
} from "../../src/api/change-control-data-source";
import { engineeringChangeCategories } from "../../src/api/change-control-data-source";

export const changeControlIds = {
  change: "91000000-0000-4000-8000-000000000001",
  event: "91000000-0000-4000-8000-000000000002",
  outbox: "91000000-0000-4000-8000-000000000003",
  project: "11111111-1111-4111-8111-111111111111",
  request: "91000000-0000-4000-8000-000000000004",
  revision: "91000000-0000-4000-8000-000000000005",
  summaryRequest: "91000000-0000-4000-8000-000000000006",
} as const;

export function engineeringChangeContent(): EngineeringChangeContent {
  return {
    title: "Gate-safe material substitution",
    reason: "The approved resin grade must be replaced before the next trial.",
    impactAssessments: engineeringChangeCategories.map((category, index) => ({
      category,
      conclusion:
        category === "product" || category === "quality"
          ? "affected"
          : "not_affected",
      responsibleUserId: "engineer@example.invalid",
      rationale:
        index < 2
          ? "A controlled successor is required."
          : "The retained evidence shows no impact.",
      evidenceReferenceGlobalIds:
        category === "quality" ? ["91000000-0000-4000-8000-000000000007"] : [],
    })),
    affectedObjects: [
      {
        category: "product",
        kind: "engineering_part_revision",
        objectGlobalId: "91000000-0000-4000-8000-000000000008",
        priorVersionGlobalId: "91000000-0000-4000-8000-000000000009",
        priorSnapshotHash: "1".repeat(64),
        successorVersionGlobalId: "91000000-0000-4000-8000-00000000000a",
        successorSnapshotHash: "2".repeat(64),
      },
    ],
    implementationTasks: [
      {
        kind: "design",
        workItemGlobalId: "91000000-0000-4000-8000-00000000000b",
        purpose: "Release the approved material successor.",
      },
    ],
    effectivityRules: [
      {
        kind: "date",
        effectiveDate: "2026-09-15",
        selectorReference: null,
        validationEvidenceGlobalId: "91000000-0000-4000-8000-00000000000c",
      },
    ],
    dispositions: [
      {
        scope: "old_inventory",
        decision: "segregate",
        approvedByUserId: "quality@example.invalid",
        approvalEvidenceGlobalId: "91000000-0000-4000-8000-00000000000d",
        executionEvidenceGlobalId: "91000000-0000-4000-8000-00000000000e",
        note: "Retain by controlled lot until disposition is verified.",
      },
    ],
    revalidationRequirements: [
      {
        kind: "trial",
        state: "satisfied",
        responsibleUserId: "quality@example.invalid",
        workItemGlobalId: "91000000-0000-4000-8000-00000000000f",
        gateReviewGlobalId: null,
        evidenceReferenceGlobalIds: ["91000000-0000-4000-8000-000000000010"],
        waiverApprovalGlobalId: null,
      },
    ],
    costSummary: {
      currency: "USD",
      engineeringCost: "1200.50",
      toolingCost: "0",
      scrapCost: "300",
      logisticsCost: "75",
      downtimeMinutes: 30,
      deliveryImpactDays: 1,
    },
    closureEvidence: {
      newVersionsReleased: true,
      erpUpdateObserved: true,
      oldVersionsWithdrawn: true,
      effectivityValidated: true,
      dispositionsExecuted: true,
      evidenceReferenceGlobalIds: ["91000000-0000-4000-8000-000000000011"],
    },
  };
}

export function engineeringChangeRevision(
  overrides: Partial<EngineeringChangeRevision> = {},
): EngineeringChangeRevision {
  return {
    schemaVersion: 1,
    globalId: changeControlIds.revision,
    changeGlobalId: changeControlIds.change,
    tenantId: "tenant-one",
    projectGlobalId: changeControlIds.project,
    revision: 1,
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    state: "ready_to_close",
    ...engineeringChangeContent(),
    formalChange: {
      doctype: "Engineering Change Request",
      documentName: "ECR-0001",
      rawStatus: "Approved",
      sourceVersion: "7",
      sourceModifiedAt: "2026-08-30T10:00:00Z",
      sourceHash: "3".repeat(64),
      observedAt: "2026-08-30T10:05:00Z",
    },
    readyToClose: true,
    createdByUserId: "engineer@example.invalid",
    createdAt: "2026-08-30T10:10:00Z",
    requestId: changeControlIds.request,
    traceId: "trace-change-control-fixture",
    snapshotHash: "4".repeat(64),
    ...overrides,
  };
}

export function engineeringChangeEvent(): EngineeringChangeEvent {
  const revision = engineeringChangeRevision();
  return {
    schemaVersion: 1,
    globalId: changeControlIds.event,
    changeGlobalId: revision.changeGlobalId,
    tenantId: revision.tenantId,
    projectGlobalId: revision.projectGlobalId,
    revisionGlobalId: revision.globalId,
    revision: revision.revision,
    revisionSnapshotHash: revision.snapshotHash,
    eventType: "ready_to_close",
    actorUserId: revision.createdByUserId,
    occurredAt: "2026-08-30T10:11:00Z",
    requestId: revision.requestId,
    traceId: revision.traceId,
    eventHash: "5".repeat(64),
  };
}

export function engineeringChangeList(
  overrides: Partial<EngineeringChangeList> = {},
): EngineeringChangeList {
  const currentRevision = engineeringChangeRevision();
  return {
    projectGlobalId: changeControlIds.project,
    items: [
      {
        currentRevision,
        change: {
          globalId: currentRevision.changeGlobalId,
          projectGlobalId: currentRevision.projectGlobalId,
          title: currentRevision.title,
          state: currentRevision.state,
          optimisticVersion: currentRevision.revision,
          currentRevisionGlobalId: currentRevision.globalId,
          currentRevisionNumber: currentRevision.revision,
          currentRevisionSnapshotHash: currentRevision.snapshotHash,
          formalChange: currentRevision.formalChange,
          readyToClose: currentRevision.readyToClose,
        },
      },
    ],
    permissions: {
      canView: true,
      canCreate: true,
      canRevise: true,
      canLinkFormalObservation: false,
      canClose: true,
    },
    ...overrides,
  };
}

export function engineeringChangeDetail(
  overrides: Partial<EngineeringChangeDetail> = {},
): EngineeringChangeDetail {
  const list = engineeringChangeList();
  const item = list.items[0];
  if (!item) throw new Error("The deterministic change fixture is required.");
  return {
    projectGlobalId: changeControlIds.project,
    change: item.change,
    currentRevision: item.currentRevision,
    revisions: [item.currentRevision],
    events: [engineeringChangeEvent()],
    permissions: list.permissions,
    ...overrides,
  };
}

export function engineeringChangeCommandResult(
  operation: EngineeringChangeCommandResult["operation"] = "engineering_change.revise",
): EngineeringChangeCommandResult {
  const detail = engineeringChangeDetail();
  return {
    operation,
    change: detail.change,
    currentRevision: detail.currentRevision,
  };
}

export function engineeringChangeSummaryReceipt(): EngineeringChangeSummaryReceipt {
  const revision = engineeringChangeRevision();
  return {
    schemaVersion: 1,
    requestGlobalId: changeControlIds.summaryRequest,
    changeGlobalId: revision.changeGlobalId,
    revisionGlobalId: revision.globalId,
    revisionNumber: revision.revision,
    sourceHash: "6".repeat(64),
    state: "queued",
    outboxEventId: changeControlIds.outbox,
  };
}
