import type {
  MbomCurrentMappingViewModel,
  MbomNodeResultViewModel,
  MbomNodeState,
  MbomRequestDetailViewModel,
  MbomRequestListViewModel,
  MbomRequestState,
  MbomTargetMode,
} from "../../src/api/mbom-publish-data-source";
import { ebomId, ebomProjectId, ebomRevisionOneId } from "./ebom-fixture";
import { publishPolicyId, publishRequestId } from "./publish-request-fixture";

export const mbomRequestId = "78000000-0000-4000-8000-000000000001";
export const mbomOutboxId = "78000000-0000-4000-8000-000000000002";
export const mbomAttemptId = "78000000-0000-4000-8000-000000000003";
export const mbomResultId = "78000000-0000-4000-8000-000000000004";
export const mbomAssemblyNodeId = "78000000-0000-4000-8000-000000000005";
export const mbomComponentNodeId = "78000000-0000-4000-8000-000000000006";
export const mbomAssemblyLineId = "78000000-0000-4000-8000-000000000007";
export const mbomComponentLineId = "78000000-0000-4000-8000-000000000008";
export const mbomNodeResultId = "78000000-0000-4000-8000-000000000009";
export const mbomSubAssemblyNodeId = "78000000-0000-4000-8000-00000000000d";
export const mbomSubAssemblyLineId = "78000000-0000-4000-8000-00000000000e";
export const mbomSubNodeResultId = "78000000-0000-4000-8000-00000000000f";

const hash = (value: string): string => value.repeat(64);
const assemblySourceKey = hash("1");
const subAssemblySourceKey = hash("2");

export function mbomPublishDetailFixture(
  options: {
    state?: MbomRequestState;
    targetMode?: MbomTargetMode;
    submittedExpectation?: boolean;
    canView?: boolean;
    canExecute?: boolean;
  } = {},
): MbomRequestDetailViewModel {
  const state = options.state ?? "synthetic_verified";
  const targetMode =
    options.targetMode ??
    (state === "validated_mock"
      ? "mock"
      : state === "succeeded" ||
          state === "partially_succeeded" ||
          state === "uncertain_after_timeout" ||
          state === "mapping_conflict"
        ? "sandbox"
        : "synthetic");
  const mock = targetMode === "mock";
  const active = ["queued", "processing", "failed_retryable"].includes(state);
  const hasResult = !mock && !active;
  const authoritative = state === "succeeded";
  const uncertain = state === "uncertain_after_timeout";
  const conflict = state === "mapping_conflict";
  const partial = state === "partially_succeeded";
  const failed = state === "failed_final";
  const submittedExpectation = options.submittedExpectation ?? false;
  const expectationMapped = submittedExpectation || targetMode === "sandbox";
  const commonNodeState: MbomNodeState = authoritative
    ? "succeeded_authoritative"
    : uncertain
      ? "uncertain_after_timeout"
      : conflict
        ? "blocked_submitted"
        : failed
          ? "failed_final"
          : partial
            ? "failed_retryable"
            : state === "synthetic_verified"
              ? "synthetic_verified"
              : state === "processing"
                ? "processing"
                : "queued";
  const rootNodeState: MbomNodeState = partial
    ? "succeeded_authoritative"
    : commonNodeState;
  const subNodeState: MbomNodeState = partial
    ? "failed_retryable"
    : commonNodeState;
  const responseAuthenticated = authoritative;
  const faultKind = uncertain
    ? "timeout_after_possible_commit"
    : conflict
      ? "submitted_bom"
      : failed || partial
        ? "target_unavailable"
        : "none";
  const request = {
    schemaVersion: 2 as const,
    apiVersion: "npi.erp-mbom-publish.v1" as const,
    operation: "publish_released_mbom" as const,
    globalId: mbomRequestId,
    source: {
      schemaVersion: 2 as const,
      tenantId: "TENANT-A",
      projectGlobalId: ebomProjectId,
      ebomGlobalId: ebomId,
      phase5PublishRequestGlobalId: publishRequestId,
      phase5PublishRequestPayloadHash: hash("2"),
      publishPolicyGlobalId: publishPolicyId,
      publishPolicyVersion: 1,
      publishPolicySnapshotHash: hash("3"),
      lifecycleVersion: 4,
      releaseEventGlobalId: "78000000-0000-4000-8000-00000000000a",
      releaseEventHash: hash("4"),
      approvalEvidenceIds: ["78000000-0000-4000-8000-00000000000b"],
      releasedAt: "2026-08-21T08:00:00Z",
      topology: {
        revisionGlobalId: ebomRevisionOneId,
        revisionNumber: 1,
        revisionSnapshotHash: hash("5"),
        lines: [
          {
            lineGlobalId: mbomAssemblyLineId,
            stableLineKey: "ROOT",
            parentLineKey: null,
            engineeringItemId: "ENG-ASSEMBLY-001",
            quantity: "1.000",
            engineeringUom: "Nos",
            alternates: [],
            effectivity: {},
            attributes: { material: "PA66" },
            lineHash: hash("6"),
            sourceRole: "assembly" as const,
          },
          {
            lineGlobalId: mbomSubAssemblyLineId,
            stableLineKey: "SUB-1",
            parentLineKey: "ROOT",
            engineeringItemId: "ENG-ASSEMBLY-002",
            quantity: "2.000",
            engineeringUom: "Nos",
            alternates: [],
            effectivity: {},
            attributes: { material: "POM" },
            lineHash: hash("7"),
            sourceRole: "assembly" as const,
          },
          {
            lineGlobalId: mbomComponentLineId,
            stableLineKey: "COMP-1",
            parentLineKey: "SUB-1",
            engineeringItemId: "ENG-COMP-001",
            quantity: "4.000",
            engineeringUom: "Nos",
            alternates: [],
            effectivity: {},
            attributes: { material: "POM" },
            lineHash: hash("8"),
            sourceRole: "component_only" as const,
          },
        ],
      },
      sourceStreamKeyHash: hash("8"),
      topologyHash: hash("9"),
      sourceHash: hash("a"),
    },
    itemReadiness: ["ENG-ASSEMBLY-001", "ENG-ASSEMBLY-002", "ENG-COMP-001"].map(
      (engineeringItemId, index) => ({
        engineeringItemId,
        disposition:
          targetMode === "sandbox"
            ? ("advanced" as const)
            : targetMode === "synthetic"
              ? ("synthetic_reference" as const)
              : ("not_ready" as const),
        itemStreamKeyHash:
          index === 0 ? hash("b") : index === 1 ? hash("c") : hash("d"),
        mappingVersion: targetMode === "sandbox" ? 1 : 0,
        formalItemCode:
          targetMode === "sandbox"
            ? `ITEM-SANDBOX-000${String(index + 1)}`
            : null,
        targetVersion: targetMode === "sandbox" ? "1" : null,
        observationHash:
          targetMode === "sandbox"
            ? index === 0
              ? hash("d")
              : index === 1
                ? hash("e")
                : hash("f")
            : null,
        authority:
          targetMode === "sandbox"
            ? ("authoritative_sandbox" as const)
            : targetMode === "synthetic"
              ? ("synthetic" as const)
              : ("none" as const),
        responseAuthenticated: targetMode === "sandbox",
        syntheticItemReference:
          targetMode === "synthetic"
            ? `synthetic-item-${String(index + 1).repeat(24)}`
            : null,
      }),
    ),
    itemMappingSetHash: hash("f"),
    mbomExpectations: [
      {
        assemblySourceKey,
        stableLineKey: "ROOT",
        mappingVersion: expectationMapped ? 1 : 0,
        submissionState: submittedExpectation
          ? ("submitted_immutable" as const)
          : expectationMapped
            ? ("editable_draft" as const)
            : ("unmapped_create" as const),
        intent: expectationMapped
          ? ("update_draft" as const)
          : ("create_draft" as const),
        formalBomId: expectationMapped ? "BOM-SANDBOX-PRIOR" : null,
        targetVersion: expectationMapped ? "1" : null,
        observationHash: expectationMapped ? hash("0") : null,
      },
      {
        assemblySourceKey: subAssemblySourceKey,
        stableLineKey: "SUB-1",
        mappingVersion: expectationMapped ? 1 : 0,
        submissionState: submittedExpectation
          ? ("submitted_immutable" as const)
          : expectationMapped
            ? ("editable_draft" as const)
            : ("unmapped_create" as const),
        intent: expectationMapped
          ? ("update_draft" as const)
          : ("create_draft" as const),
        formalBomId: expectationMapped ? "BOM-SANDBOX-PRIOR-SUB" : null,
        targetVersion: expectationMapped ? "1" : null,
        observationHash: expectationMapped ? hash("a") : null,
      },
    ],
    mbomMappingSetHash: hash("1"),
    profile: {
      profileId: `mbom-${targetMode}-v1`,
      profileVersion: 1,
      targetMode,
      environmentCode:
        targetMode === "synthetic" ? "disposable-test" : targetMode,
      projectionPolicyId: "mbom-projection-v1",
      projectionPolicyVersion: 1,
      projectionPolicyHash: hash("2"),
      snapshotHash: hash("3"),
    },
    actorUserId: "publisher@example.invalid",
    serviceActorUserId: mock ? null : "worker@example.invalid",
    requestId: "78000000-0000-4000-8000-00000000000c",
    traceId: "trace-p8-04-mbom-fixture",
    idempotencyKeyHash: hash("4"),
    targetIdempotencyKeyHash: hash("5"),
    semanticEffectHash: hash("6"),
    state,
    dispatchAllowed: !mock,
    payloadHash: hash("7"),
    createdAt: "2026-08-21T08:00:00Z",
  };
  const [rootLine, subLine, componentLine] = request.source.topology.lines;
  const [rootReadiness, subReadiness, componentReadiness] =
    request.itemReadiness;
  const [rootExpectation, subExpectation] = request.mbomExpectations;
  if (
    !rootLine ||
    !subLine ||
    !componentLine ||
    !rootReadiness ||
    !subReadiness ||
    !componentReadiness ||
    !rootExpectation ||
    !subExpectation
  ) {
    throw new Error("The MBOM fixture topology is incomplete.");
  }
  const outboxEventId = mock ? null : mbomOutboxId;
  const assemblyNode = {
    globalId: mbomAssemblyNodeId,
    requestGlobalId: mbomRequestId,
    line: rootLine,
    itemReadiness: rootReadiness,
    mbomExpectation: rootExpectation,
    state: mock ? ("blocked_item_mapping" as const) : rootNodeState,
    nodeSnapshotHash: hash("8"),
  };
  const subAssemblyNode = {
    globalId: mbomSubAssemblyNodeId,
    requestGlobalId: mbomRequestId,
    line: subLine,
    itemReadiness: subReadiness,
    mbomExpectation: subExpectation,
    state: mock ? ("blocked_item_mapping" as const) : subNodeState,
    nodeSnapshotHash: hash("a"),
  };
  const componentNode = {
    globalId: mbomComponentNodeId,
    requestGlobalId: mbomRequestId,
    line: componentLine,
    itemReadiness: componentReadiness,
    mbomExpectation: null,
    state: "component_only" as const,
    nodeSnapshotHash: hash("9"),
  };
  const nodeResults: MbomNodeResultViewModel[] = hasResult
    ? [
        {
          schemaVersion: 1,
          globalId: mbomNodeResultId,
          requestGlobalId: mbomRequestId,
          resultGlobalId: mbomResultId,
          attemptGlobalId: mbomAttemptId,
          nodeGlobalId: mbomAssemblyNodeId,
          stableLineKey: "ROOT",
          assemblySourceKey,
          state: rootNodeState as MbomNodeResultViewModel["state"],
          authority:
            rootNodeState === "succeeded_authoritative"
              ? "authoritative_sandbox"
              : rootNodeState === "synthetic_verified"
                ? "synthetic"
                : "none",
          responseAuthenticated: rootNodeState === "succeeded_authoritative",
          responseHash: hash("a"),
          formalBomId:
            rootNodeState === "succeeded_authoritative"
              ? "BOM-SANDBOX-0001"
              : null,
          targetVersion:
            rootNodeState === "succeeded_authoritative" ? "7" : null,
          targetSubmissionState:
            rootNodeState === "succeeded_authoritative"
              ? "editable_draft"
              : null,
          faultKind:
            rootNodeState === "succeeded_authoritative" ||
            rootNodeState === "synthetic_verified"
              ? "none"
              : faultKind,
          observedAt: "2026-08-21T08:00:02Z",
          nodeResultHash: hash("b"),
        },
        {
          schemaVersion: 1,
          globalId: mbomSubNodeResultId,
          requestGlobalId: mbomRequestId,
          resultGlobalId: mbomResultId,
          attemptGlobalId: mbomAttemptId,
          nodeGlobalId: mbomSubAssemblyNodeId,
          stableLineKey: "SUB-1",
          assemblySourceKey: subAssemblySourceKey,
          state: subNodeState as MbomNodeResultViewModel["state"],
          authority:
            subNodeState === "succeeded_authoritative"
              ? "authoritative_sandbox"
              : subNodeState === "synthetic_verified"
                ? "synthetic"
                : "none",
          responseAuthenticated: subNodeState === "succeeded_authoritative",
          responseHash: hash("c"),
          formalBomId:
            subNodeState === "succeeded_authoritative"
              ? "BOM-SANDBOX-0002"
              : null,
          targetVersion:
            subNodeState === "succeeded_authoritative" ? "3" : null,
          targetSubmissionState:
            subNodeState === "succeeded_authoritative"
              ? "editable_draft"
              : null,
          faultKind:
            subNodeState === "succeeded_authoritative" ||
            subNodeState === "synthetic_verified"
              ? "none"
              : faultKind,
          observedAt: "2026-08-21T08:00:02Z",
          nodeResultHash: hash("d"),
        },
      ]
    : [];
  const currentMappings: MbomCurrentMappingViewModel[] = nodeResults.flatMap(
    (nodeResult, index) => {
      if (
        nodeResult.state !== "succeeded_authoritative" ||
        nodeResult.formalBomId === null ||
        nodeResult.targetVersion === null
      )
        return [];
      return [
        {
          stableLineKey: nodeResult.stableLineKey,
          assemblySourceKey: nodeResult.assemblySourceKey,
          mappingVersion: 2,
          formalBomId: nodeResult.formalBomId,
          targetVersion: nodeResult.targetVersion,
          targetSubmissionState: "editable_draft",
          authority: "authoritative_sandbox",
          responseAuthenticated: true,
          observationHash: index === 0 ? hash("c") : hash("e"),
          updatedAt: "2026-08-21T08:00:02Z",
        },
      ];
    },
  );
  return {
    requestGlobalId: mbomRequestId,
    request,
    outboxEventId,
    updatedAt: "2026-08-21T08:00:02Z",
    nodes: [assemblyNode, subAssemblyNode, componentNode],
    attempts:
      mock || state === "queued"
        ? []
        : [
            {
              globalId: mbomAttemptId,
              requestGlobalId: mbomRequestId,
              outboxEventId: mbomOutboxId,
              attemptNumber: 1,
              state:
                state === "processing"
                  ? "started"
                  : state === "synthetic_verified"
                    ? "synthetic_verified"
                    : uncertain
                      ? "uncertain"
                      : partial
                        ? "observed_partial"
                        : authoritative
                          ? "observed_success"
                          : "observed_failure",
              adapterBoundaryCrossed: state !== "processing",
              transportDisposition: hasResult ? "response_observed" : null,
              responseHash: hasResult ? hash("d") : null,
              faultKind: hasResult ? faultKind : null,
              reconciliationRequired: uncertain,
              safeErrorCode: uncertain
                ? "MBOM_PUBLISH_UNCERTAIN_AFTER_TIMEOUT"
                : null,
              startedAt: "2026-08-21T08:00:01Z",
              finishedAt:
                state === "processing" ? null : "2026-08-21T08:00:02Z",
              attemptHash: hash("e"),
            },
          ],
    result: hasResult
      ? {
          schemaVersion: 1,
          globalId: mbomResultId,
          requestGlobalId: mbomRequestId,
          outboxEventId: mbomOutboxId,
          attemptGlobalId: mbomAttemptId,
          attemptNumber: 1,
          sourceHash: request.source.sourceHash,
          topologyHash: request.source.topologyHash,
          itemMappingSetHash: request.itemMappingSetHash,
          mbomMappingSetHash: request.mbomMappingSetHash,
          state: state as Exclude<
            MbomRequestState,
            "validated_mock" | "queued" | "processing"
          >,
          authority: authoritative
            ? "authoritative_sandbox"
            : state === "synthetic_verified"
              ? "synthetic"
              : "none",
          responseAuthenticated,
          responseHash: hash("d"),
          faultKind,
          nodeResultSetHash: hash("f"),
          observedAt: "2026-08-21T08:00:02Z",
          resultHash: hash("0"),
        }
      : null,
    nodeResults,
    currentMappings,
    permissions: {
      canView: options.canView ?? true,
      canExecute: options.canExecute ?? true,
    },
  };
}

export function mbomPublishListFixture(
  detail: MbomRequestDetailViewModel | null = mbomPublishDetailFixture(),
  options: {
    profileUnavailable?: boolean;
    canView?: boolean;
    canExecute?: boolean;
  } = {},
): MbomRequestListViewModel {
  return {
    projectGlobalId: detail?.request.source.projectGlobalId ?? ebomProjectId,
    phase5PublishRequestGlobalId:
      detail?.request.source.phase5PublishRequestGlobalId ?? publishRequestId,
    permissions: {
      canView: options.canView ?? detail?.permissions.canView ?? true,
      canExecute: options.canExecute ?? detail?.permissions.canExecute ?? true,
    },
    executionProfile: options.profileUnavailable
      ? null
      : (detail?.request.profile ?? null),
    createContext:
      options.profileUnavailable || !detail
        ? null
        : {
            phase5PublishRequestGlobalId:
              detail.request.source.phase5PublishRequestGlobalId,
            source: detail.request.source,
            itemReadiness: detail.request.itemReadiness,
            itemMappingSetHash: detail.request.itemMappingSetHash,
            mbomExpectations: detail.request.mbomExpectations,
            mbomMappingSetHash: detail.request.mbomMappingSetHash,
            profile: detail.request.profile,
          },
    items: detail
      ? [
          {
            requestGlobalId: detail.requestGlobalId,
            request: detail.request,
            outboxEventId: detail.outboxEventId,
            updatedAt: detail.updatedAt,
          },
        ]
      : [],
  };
}
