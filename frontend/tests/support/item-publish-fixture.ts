import type {
  ItemPublishRequestDetailViewModel,
  ItemPublishRequestListViewModel,
  ItemPublishRequestState,
  ItemPublishTargetMode,
} from "../../src/api/item-publish-data-source";
import {
  publishNodeId,
  publishRequestFixture,
  publishRequestId,
} from "./publish-request-fixture";
import { ebomProjectId } from "./ebom-fixture";

export const itemPublishRequestId = "76000000-0000-4000-8000-000000000001";
export const itemPublishAttemptId = "76000000-0000-4000-8000-000000000002";
export const itemPublishResultId = "76000000-0000-4000-8000-000000000003";
export const itemPublishOutboxId = "76000000-0000-4000-8000-000000000004";

const hash = (character: string): string => character.repeat(64);

export function itemPublishDetailFixture(
  options: {
    state?: ItemPublishRequestState;
    targetMode?: ItemPublishTargetMode;
    authoritativeMapping?: boolean;
  } = {},
): ItemPublishRequestDetailViewModel {
  const phase5 = publishRequestFixture();
  const node = phase5.nodes[0];
  if (!node) throw new Error("The Item fixture requires one publish node.");
  const state =
    options.state ??
    (options.targetMode === "mock" ? "validated_mock" : "synthetic_verified");
  const mappingConflict = state === "mapping_conflict";
  const targetMode =
    options.targetMode ?? (mappingConflict ? "sandbox" : "synthetic");
  const mock = targetMode === "mock";
  const hasResult =
    state !== "queued" && state !== "processing" && state !== "validated_mock";
  const authoritative =
    Boolean(options.authoritativeMapping) || mappingConflict;
  const resultState =
    state === "synthetic_verified" ||
    state === "succeeded" ||
    state === "failed_retryable" ||
    state === "failed_final" ||
    state === "uncertain_after_timeout"
      ? state
      : "succeeded";
  const outboxEventId = mock ? null : itemPublishOutboxId;
  const request = {
    schemaVersion: 1 as const,
    globalId: itemPublishRequestId,
    apiVersion: "npi.erp-item-publish.v1" as const,
    operation: "publish_released_item" as const,
    source: {
      schemaVersion: 1 as const,
      tenantId: "TENANT-A",
      projectGlobalId: ebomProjectId,
      engineeringItemId: node.line.engineeringItemId,
      selectedPublishNodeGlobalId: publishNodeId,
      itemMaster: {
        description: node.line.description,
        engineeringUom: node.line.engineeringUom,
        attributes: node.line.attributes,
      },
      occurrences: [
        {
          publishNodeGlobalId: publishNodeId,
          lineGlobalId: node.line.globalId,
          engineeringItemId: node.line.engineeringItemId,
          description: node.line.description,
          engineeringUom: node.line.engineeringUom,
          attributes: node.line.attributes,
          lineHash: node.line.lineHash,
          nodeInputHash: node.inputHash,
        },
      ],
      streamKeyHash: hash("1"),
      sourceHash: hash("2"),
    },
    releasedEvidence: {
      publishRequestGlobalId: publishRequestId,
      publishRequestPayloadHash: phase5.payloadHash,
      publishPolicyGlobalId: phase5.policy.globalId,
      publishPolicyVersion: phase5.policy.version,
      publishPolicySnapshotHash: phase5.policy.snapshotHash,
      ebomGlobalId: phase5.releasedEbom.ebomGlobalId,
      ebomVersion: phase5.releasedEbom.ebomVersion,
      revisionGlobalId: phase5.releasedEbom.revisionGlobalId,
      revisionNumber: phase5.releasedEbom.revisionNumber,
      revisionSnapshotHash: phase5.releasedEbom.revisionSnapshotHash,
      lifecycleVersion: phase5.releasedEbom.lifecycleVersion,
      releaseEventGlobalId: phase5.releasedEbom.releaseEventGlobalId,
      releaseEventHash: phase5.releasedEbom.releaseEventHash,
      approvalEvidenceIds: phase5.releasedEbom.approvalEvidenceIds,
      releasedAt: phase5.releasedEbom.releasedAt,
    },
    profile: {
      profileId: `item-${targetMode}-v1`,
      profileVersion: 1,
      targetMode,
      environmentCode:
        targetMode === "synthetic" ? "disposable-test" : targetMode,
      snapshotHash: hash("3"),
    },
    mappingExpectation: {
      mappingVersion: authoritative && !mappingConflict ? 1 : 0,
      formalItemCode:
        authoritative && !mappingConflict ? "ITEM-SANDBOX-0001" : null,
      targetVersion: authoritative && !mappingConflict ? "7" : null,
      observationHash: authoritative && !mappingConflict ? hash("4") : null,
    },
    intent:
      authoritative && !mappingConflict
        ? ("update_item_engineering_fields" as const)
        : ("create_item" as const),
    actorUserId: "publisher@example.invalid",
    requestId: "76000000-0000-4000-8000-000000000005",
    traceId: "trace-p8-03-item-fixture",
    idempotencyKeyHash: hash("5"),
    payloadHash: hash("6"),
    state,
    dispatchAllowed: !mock,
    outboxEventId,
    resultGlobalId: hasResult ? itemPublishResultId : null,
    optimisticVersion: 2,
    createdAt: "2026-08-16T08:00:00Z",
    updatedAt: "2026-08-16T08:00:02Z",
  };
  const attempts = mock
    ? []
    : [
        {
          globalId: itemPublishAttemptId,
          requestGlobalId: itemPublishRequestId,
          outboxEventId: itemPublishOutboxId,
          attemptNumber: 1,
          state:
            state === "uncertain_after_timeout"
              ? ("uncertain" as const)
              : hasResult
                ? resultState === "synthetic_verified"
                  ? ("synthetic_verified" as const)
                  : resultState === "succeeded"
                    ? ("observed_success" as const)
                    : ("observed_failure" as const)
                : ("started" as const),
          adapterBoundaryCrossed: targetMode === "sandbox",
          targetIdempotencyKeyHash: hash("7"),
          requestSnapshotHash: hash("8"),
          startedAt: "2026-08-16T08:00:01Z",
          finishedAt: hasResult ? "2026-08-16T08:00:02Z" : null,
          targetStatusCode: resultState === "succeeded" ? 201 : null,
          responseHash: hasResult ? hash("9") : null,
          faultKind:
            state === "uncertain_after_timeout"
              ? "timeout_after_possible_commit"
              : "none",
          reconciliationRequired: state === "uncertain_after_timeout",
          safeErrorCode:
            state === "uncertain_after_timeout"
              ? "ITEM_PUBLISH_UNCERTAIN_AFTER_TIMEOUT"
              : null,
          attemptHash: hash("a"),
        },
      ];
  const result = hasResult
    ? {
        globalId: itemPublishResultId,
        requestGlobalId: itemPublishRequestId,
        outboxEventId: itemPublishOutboxId,
        attemptGlobalId: itemPublishAttemptId,
        attemptNumber: 1,
        sourceHash: hash("2"),
        state: resultState,
        authority: authoritative
          ? ("authoritative_sandbox" as const)
          : state === "synthetic_verified"
            ? ("synthetic" as const)
            : ("none" as const),
        responseAuthenticated: authoritative,
        responseHash: hash("9"),
        formalItemCode: authoritative ? "ITEM-SANDBOX-0001" : null,
        targetVersion: authoritative ? (mappingConflict ? "2" : "7") : null,
        faultKind:
          state === "uncertain_after_timeout"
            ? "timeout_after_possible_commit"
            : "none",
        resultHash: hash("b"),
        observedAt: "2026-08-16T08:00:02Z",
      }
    : null;
  return {
    requestGlobalId: itemPublishRequestId,
    request,
    currentMapping: authoritative
      ? mappingConflict
        ? {
            mappingVersion: 1,
            formalItemCode: "ITEM-SANDBOX-0001",
            targetVersion: "1",
            observationHash: hash("c"),
          }
        : {
            mappingVersion: 2,
            formalItemCode: "ITEM-SANDBOX-0001",
            targetVersion: "7",
            observationHash: hash("c"),
          }
      : null,
    attempts,
    result,
    permissions: { canView: true, canExecute: true },
  };
}

export function itemPublishListFixture(
  detail: ItemPublishRequestDetailViewModel | null = itemPublishDetailFixture(),
  options: {
    canExecute?: boolean;
    profileMode?: ItemPublishTargetMode;
    profileUnavailable?: boolean;
    mappingExpectation?: ItemPublishRequestListViewModel["mappingExpectation"];
  } = {},
): ItemPublishRequestListViewModel {
  const profileMode =
    options.profileMode ?? detail?.request.profile.targetMode ?? "synthetic";
  return {
    projectGlobalId: ebomProjectId,
    sourceFilters: {
      publishRequestGlobalId: publishRequestId,
      selectedPublishNodeGlobalId: publishNodeId,
    },
    permissions: { canView: true, canExecute: options.canExecute ?? true },
    executionProfile: options.profileUnavailable
      ? null
      : {
          profileId: `item-${profileMode}-v1`,
          profileVersion: 1,
          targetMode: profileMode,
          environmentCode:
            profileMode === "synthetic" ? "disposable-test" : profileMode,
          snapshotHash: hash("3"),
        },
    mappingExpectation: options.mappingExpectation ??
      detail?.request.mappingExpectation ?? {
        mappingVersion: 0,
        formalItemCode: null,
        targetVersion: null,
        observationHash: null,
      },
    items: detail ? [detail.request] : [],
  };
}
