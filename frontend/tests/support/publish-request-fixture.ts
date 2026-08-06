import type {
  EngineeringBomPublishRequestListViewModel,
  EngineeringBomPublishRequestViewModel,
  PublishNodeState,
} from "../../src/api/publish-request-data-source";
import {
  ebomId,
  ebomPolicyId,
  ebomProjectId,
  ebomRevisionOneId,
  engineeringBomDetailFixture,
  engineeringBomListFixture,
  releasedEngineeringBomRevisionFixture,
} from "./ebom-fixture";

export const publishPolicyId = "75000000-0000-4000-8000-000000000020";
export const publishRequestId = "75000000-0000-4000-8000-000000000021";
export const publishNodeId = "75000000-0000-4000-8000-000000000022";
export const publishResultId = "75000000-0000-4000-8000-000000000023";
export const publishCommandRequestId = "75000000-0000-4000-8000-000000000024";
const approvalEvidenceId = "75000000-0000-4000-8000-000000000025";
const hashA = "a".repeat(64);
const hashB = "b".repeat(64);
const hashD = "d".repeat(64);
const hashE = "e".repeat(64);
const hashF = "f".repeat(64);

export function publishRequestFixture(
  options: {
    requestState?: "validated" | "manual_intervention";
    nodeState?: PublishNodeState;
  } = {},
): EngineeringBomPublishRequestViewModel {
  const released = releasedEngineeringBomRevisionFixture();
  const line = released.lines[0];
  if (!line) throw new Error("The publish fixture requires one released line.");
  const nodeState = options.nodeState ?? "validated";
  const faultKind =
    nodeState === "target_unavailable"
      ? "target_unavailable"
      : nodeState === "failed_retryable"
        ? "target_server_error"
        : null;
  return {
    globalId: publishRequestId,
    operation: "publish_released_ebom_item_mbom",
    apiVersion: "npi.erp-publish.v1",
    policy: {
      globalId: publishPolicyId,
      version: 1,
      snapshotHash: hashD,
    },
    releasedEbom: {
      projectGlobalId: ebomProjectId,
      ebomGlobalId: ebomId,
      ebomVersion: 2,
      revisionGlobalId: ebomRevisionOneId,
      revisionNumber: 1,
      revisionSnapshotHash: hashB,
      lifecycleVersion: 4,
      releaseEventGlobalId: "75000000-0000-4000-8000-000000000010",
      releaseEventHash: "c".repeat(64),
      ebomPolicyGlobalId: ebomPolicyId,
      ebomPolicyVersion: 1,
      ebomPolicySnapshotHash: hashA,
      approvalEvidenceIds: [approvalEvidenceId],
      releasedAt: "2026-08-05T08:30:00Z",
    },
    targetMode: "mock",
    state: options.requestState ?? "validated",
    dispatchAllowed: false,
    actorUserId: "publisher@example.invalid",
    requestId: publishCommandRequestId,
    traceId: "trace-p5-05-publish-fixture",
    payloadHash: hashE,
    ownedFields: [
      "engineering_item_id",
      "engineering_description",
      "ebom_hierarchy",
      "engineering_quantity",
      "engineering_uom",
    ],
    nodes: [
      {
        globalId: publishNodeId,
        line: {
          ...line,
          lineHash: hashF,
        },
        mapping: {
          state: "unmapped",
          version: 0,
          formalItemCode: null,
          formalMbomId: null,
          targetVersion: null,
          observedAt: null,
        },
        operations: ["create_item", "create_or_update_mbom"],
        resultState: nodeState,
        inputHash: hashE,
        results: [
          {
            globalId: publishResultId,
            nodeGlobalId: publishNodeId,
            nodeInputHash: hashE,
            attemptNumber: 0,
            state: nodeState,
            faultKind,
            futureRetryDirective:
              nodeState === "target_unavailable"
                ? "reconcile_before_retry"
                : nodeState === "failed_retryable"
                  ? "retry_same_idempotency"
                  : "none",
            futureRetryable: nodeState === "failed_retryable",
            reconciliationRequired: nodeState === "target_unavailable",
            retryAfterRequired: false,
            phase5DispatchAllowed: false,
            formalItemCode: null,
            formalMbomId: null,
            targetVersion: null,
            occurredAt: "2026-08-06T10:00:00Z",
            resultHash: hashF,
          },
        ],
      },
    ],
    capabilities: {
      view: true,
      create: true,
      dispatch: false,
      retry: false,
      reconcile: false,
    },
    createdAt: "2026-08-06T10:00:00Z",
  };
}

export function publishRequestListFixture(
  request: EngineeringBomPublishRequestViewModel = publishRequestFixture(),
): EngineeringBomPublishRequestListViewModel {
  const project = engineeringBomListFixture().project;
  const ebom = engineeringBomDetailFixture().ebom;
  const released = releasedEngineeringBomRevisionFixture();
  return {
    project,
    ebom,
    revision: {
      globalId: released.globalId,
      revisionNumber: released.revisionNumber,
      snapshotHash: released.snapshotHash,
    },
    permissions: { view: true, create: true },
    policies: [
      {
        globalId: publishPolicyId,
        version: 1,
        snapshotHash: hashD,
        key: "synthetic.publish.mock",
        title: "Synthetic Mock publish policy",
        targetMode: "mock",
      },
    ],
    items: [request],
  };
}
