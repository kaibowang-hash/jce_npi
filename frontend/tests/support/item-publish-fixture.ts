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
export const itemPublishObservationId = "76000000-0000-4000-8000-000000000006";
export const itemPublishHeadId = "76000000-0000-4000-8000-000000000007";
export const itemPublishPriorRequestId = "76000000-0000-4000-8000-000000000008";
export const itemPublishPriorOutboxId = "76000000-0000-4000-8000-000000000009";
export const itemPublishPriorAttemptId = "76000000-0000-4000-8000-00000000000a";
export const itemPublishPriorResultId = "76000000-0000-4000-8000-00000000000b";
export const itemPublishPriorObservationId =
  "76000000-0000-4000-8000-00000000000c";
export const itemPublishSiblingNodeId = "76000000-0000-4000-8000-00000000000d";
export const itemPublishSiblingLineId = "76000000-0000-4000-8000-00000000000e";
export const itemPublishLaterRequestId = "76000000-0000-4000-8000-00000000000f";
export const itemPublishLaterOutboxId = "76000000-0000-4000-8000-000000000010";
export const itemPublishLaterAttemptId = "76000000-0000-4000-8000-000000000011";
export const itemPublishLaterResultId = "76000000-0000-4000-8000-000000000012";
export const itemPublishLaterObservationId =
  "76000000-0000-4000-8000-000000000013";

const hash = (character: string): string => character.repeat(64);

export function itemPublishDetailFixture(
  options: {
    state?: ItemPublishRequestState;
    targetMode?: ItemPublishTargetMode;
    authoritativeMapping?: boolean;
    mapped?: boolean;
    mappingOrigin?: "selected" | "prior" | "later";
  } = {},
): ItemPublishRequestDetailViewModel {
  const phase5 = publishRequestFixture();
  const node = phase5.nodes[0];
  if (!node) throw new Error("The Item fixture requires one publish node.");
  const sibling = {
    ...node,
    globalId: itemPublishSiblingNodeId,
    line: { ...node.line, globalId: itemPublishSiblingLineId },
  };
  const state =
    options.state ??
    (options.targetMode === "mock" ? "validated_mock" : "synthetic_verified");
  const mappingConflict = state === "mapping_conflict";
  const succeeded = state === "succeeded";
  const targetMode =
    options.targetMode ??
    (state === "validated_mock"
      ? "mock"
      : succeeded || mappingConflict || state === "uncertain_after_timeout"
        ? "sandbox"
        : "synthetic");
  const mock = targetMode === "mock";
  const hasResult = !["validated_mock", "queued", "processing"].includes(state);
  const mappingOrigin =
    options.mappingOrigin ??
    (succeeded
      ? "selected"
      : mappingConflict || options.mapped || options.authoritativeMapping
        ? "prior"
        : undefined);
  const mapped = mappingOrigin !== undefined;
  const authoritative =
    targetMode === "sandbox" && (succeeded || mappingConflict);
  const resultState =
    state === "synthetic_verified" ||
    state === "succeeded" ||
    state === "failed_retryable" ||
    state === "failed_final" ||
    state === "uncertain_after_timeout"
      ? state
      : "succeeded";
  const outboxEventId = mock ? null : itemPublishOutboxId;
  const expectationVersion = succeeded || (mapped && !mappingConflict) ? 1 : 0;
  const expectationCode = expectationVersion > 0 ? "ITEM-SANDBOX-0001" : null;
  const expectationTarget = expectationVersion > 0 ? "1" : null;
  const expectationObservationHash = expectationVersion > 0 ? hash("e") : null;
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
      occurrences: [node, sibling].map((item) => ({
        publishNodeGlobalId: item.globalId,
        lineGlobalId: item.line.globalId,
        engineeringItemId: item.line.engineeringItemId,
        description: item.line.description,
        engineeringUom: item.line.engineeringUom,
        attributes: item.line.attributes,
        lineHash: item.line.lineHash,
        nodeInputHash: item.inputHash,
      })),
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
      mappingVersion: expectationVersion,
      formalItemCode: succeeded ? "ITEM-SANDBOX-0001" : expectationCode,
      targetVersion: succeeded ? "7" : expectationTarget,
      observationHash: succeeded ? hash("4") : expectationObservationHash,
    },
    intent:
      expectationVersion > 0
        ? ("update_item_engineering_fields" as const)
        : ("create_item" as const),
    actorUserId: "publisher@example.invalid",
    requestId: "76000000-0000-4000-8000-000000000005",
    traceId: "trace-p8-03-item-fixture",
    idempotencyKeyHash: hash("5"),
    payloadHash: hash("6"),
    state,
    dispatchAllowed: !mock,
    legacyReadOnly: false,
    current: true,
    outboxEventId,
    resultGlobalId: hasResult ? itemPublishResultId : null,
    optimisticVersion: 2,
    createdAt: "2026-08-16T08:00:00Z",
    updatedAt: "2026-08-16T08:00:02Z",
  };

  const attemptState =
    state === "processing"
      ? ("started" as const)
      : state === "synthetic_verified"
        ? ("synthetic_verified" as const)
        : state === "succeeded" || state === "mapping_conflict"
          ? ("observed_success" as const)
          : state === "uncertain_after_timeout"
            ? ("uncertain" as const)
            : ("observed_failure" as const);
  const hasAttempt = !mock && state !== "queued";
  const faultKind =
    state === "uncertain_after_timeout"
      ? "timeout_after_possible_commit"
      : state === "failed_retryable" || state === "failed_final"
        ? "target_unavailable"
        : "none";
  const attempts = hasAttempt
    ? [
        {
          globalId: itemPublishAttemptId,
          requestGlobalId: itemPublishRequestId,
          outboxEventId: itemPublishOutboxId,
          attemptNumber: 1,
          sourceHash: hash("2"),
          profileId: `item-${targetMode}-v1`,
          profileVersion: 1,
          state: attemptState,
          adapterBoundaryCrossed: state !== "processing",
          targetIdempotencyKeyHash: hash("7"),
          requestSnapshotHash: hash("8"),
          startedAt: "2026-08-16T08:00:01Z",
          finishedAt: state === "processing" ? null : "2026-08-16T08:00:02Z",
          targetStatusCode:
            state === "succeeded" || state === "mapping_conflict" ? 201 : null,
          responseHash: hasResult ? hash("9") : null,
          faultKind,
          reconciliationRequired: state === "uncertain_after_timeout",
          safeErrorCode:
            state === "uncertain_after_timeout"
              ? "ITEM_PUBLISH_UNCERTAIN_AFTER_TIMEOUT"
              : null,
          attemptHash: hash("a"),
        },
      ]
    : [];

  const result = hasResult
    ? {
        globalId: itemPublishResultId,
        requestGlobalId: itemPublishRequestId,
        outboxEventId: itemPublishOutboxId,
        attemptGlobalId: itemPublishAttemptId,
        attemptNumber: 1,
        idempotencyKeyHash: hash("7"),
        sourceHash: hash("2"),
        expectedTargetVersion: succeeded
          ? "7"
          : expectationVersion > 0
            ? expectationTarget
            : null,
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
        faultKind,
        resultHash: hash("b"),
        observedAt: "2026-08-16T08:00:02Z",
      }
    : null;

  const priorMapping = {
    head: {
      globalId: itemPublishHeadId,
      sourceStreamKeyHash: hash("1"),
      engineeringItemId: node.line.engineeringItemId,
      mappingVersion: 1,
      formalItemCode: "ITEM-SANDBOX-0001",
      targetVersion: "1",
      currentObservationGlobalId: itemPublishPriorObservationId,
      currentObservationHash: hash("c"),
      headHash: hash("d"),
      updatedAt: "2026-08-16T07:59:02Z",
    },
    observation: {
      globalId: itemPublishPriorObservationId,
      sourceStreamKeyHash: hash("1"),
      engineeringItemId: node.line.engineeringItemId,
      mappingVersion: 1,
      formalItemCode: "ITEM-SANDBOX-0001",
      targetVersion: "1",
      requestGlobalId: itemPublishPriorRequestId,
      outboxEventId: itemPublishPriorOutboxId,
      attemptGlobalId: itemPublishPriorAttemptId,
      resultGlobalId: itemPublishPriorResultId,
      profileId: "item-sandbox-v1",
      profileVersion: 1,
      environmentCode: "sandbox",
      authority: "authoritative_sandbox" as const,
      disposition: "advanced" as const,
      previousMappingVersion: 0,
      previousObservationHash: null,
      targetResultHash: hash("e"),
      observationHash: hash("c"),
      observedAt: "2026-08-16T07:59:02Z",
    },
  };
  const selectedMapping = {
    head: {
      globalId: itemPublishHeadId,
      sourceStreamKeyHash: hash("1"),
      engineeringItemId: node.line.engineeringItemId,
      mappingVersion: 2,
      formalItemCode: "ITEM-SANDBOX-0001",
      targetVersion: "7",
      currentObservationGlobalId: itemPublishObservationId,
      currentObservationHash: hash("c"),
      headHash: hash("d"),
      updatedAt: "2026-08-16T08:00:02Z",
    },
    observation: {
      globalId: itemPublishObservationId,
      sourceStreamKeyHash: hash("1"),
      engineeringItemId: node.line.engineeringItemId,
      mappingVersion: 2,
      formalItemCode: "ITEM-SANDBOX-0001",
      targetVersion: "7",
      requestGlobalId: itemPublishRequestId,
      outboxEventId: itemPublishOutboxId,
      attemptGlobalId: itemPublishAttemptId,
      resultGlobalId: itemPublishResultId,
      profileId: "item-sandbox-v1",
      profileVersion: 1,
      environmentCode: "sandbox",
      authority: "authoritative_sandbox" as const,
      disposition: "advanced" as const,
      previousMappingVersion: 1,
      previousObservationHash: hash("4"),
      targetResultHash: hash("b"),
      observationHash: hash("c"),
      observedAt: "2026-08-16T08:00:02Z",
    },
  };
  const laterMapping = {
    head: {
      globalId: itemPublishHeadId,
      sourceStreamKeyHash: hash("1"),
      engineeringItemId: node.line.engineeringItemId,
      mappingVersion: 2,
      formalItemCode: "ITEM-SANDBOX-0002",
      targetVersion: "2",
      currentObservationGlobalId: itemPublishLaterObservationId,
      currentObservationHash: hash("f"),
      headHash: hash("0"),
      updatedAt: "2026-08-16T08:01:02Z",
    },
    observation: {
      globalId: itemPublishLaterObservationId,
      sourceStreamKeyHash: hash("1"),
      engineeringItemId: node.line.engineeringItemId,
      mappingVersion: 2,
      formalItemCode: "ITEM-SANDBOX-0002",
      targetVersion: "2",
      requestGlobalId: itemPublishLaterRequestId,
      outboxEventId: itemPublishLaterOutboxId,
      attemptGlobalId: itemPublishLaterAttemptId,
      resultGlobalId: itemPublishLaterResultId,
      profileId: "item-sandbox-v1",
      profileVersion: 1,
      environmentCode: "sandbox",
      authority: "authoritative_sandbox" as const,
      disposition: "advanced" as const,
      previousMappingVersion: 1,
      previousObservationHash: hash("c"),
      targetResultHash: hash("0"),
      observationHash: hash("f"),
      observedAt: "2026-08-16T08:01:02Z",
    },
  };
  const currentMapping =
    mappingOrigin === "selected"
      ? selectedMapping
      : mappingOrigin === "later"
        ? laterMapping
        : mappingOrigin === "prior"
          ? priorMapping
          : null;

  return {
    requestGlobalId: itemPublishRequestId,
    request,
    currentMapping,
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

export function itemPublishLegacyDetailFixture(): ItemPublishRequestDetailViewModel {
  const detail = itemPublishDetailFixture({
    state: "queued",
    targetMode: "sandbox",
  });
  return {
    requestGlobalId: detail.requestGlobalId,
    request: {
      ...detail.request,
      dispatchAllowed: false,
      legacyReadOnly: true,
      current: false,
      outboxEventId: null,
      resultGlobalId: null,
      state: "queued",
    },
    currentMapping: null,
    attempts: [],
    result: null,
    permissions: { canView: true, canExecute: false },
  };
}
