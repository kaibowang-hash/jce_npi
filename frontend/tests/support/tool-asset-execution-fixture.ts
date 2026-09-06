import type {
  ToolAssetExecutionCollection,
  ToolAssetExecutionContext,
  ToolAssetExecutionDetail,
} from "../../src/api/tool-asset-execution-data-source";
import { toolingAcceptanceIds as ids } from "./tooling-acceptance-fixture";

export const toolAssetExecutionRequestId =
  "79000000-0000-4000-8000-000000000001";
export const toolAssetExecutionResultId =
  "79000000-0000-4000-8000-000000000002";
export const toolAssetExecutionAttemptId =
  "79000000-0000-4000-8000-000000000003";
const hash = (value: string): string => value.repeat(64).slice(0, 64);

export function toolAssetExecutionContext(): ToolAssetExecutionContext {
  return {
    operation: "create_tool_asset",
    source: {
      projectGlobalId: ids.project,
      toolingMasterGlobalId: ids.master,
      toolingSetGlobalId: ids.set,
      acceptanceRevisionGlobalId: ids.acceptanceRevision,
      sourceHash: hash("1"),
    },
    expectedSourceHash: hash("1"),
    approval: { state: "verified" },
    expectedApprovalHash: hash("2"),
    mappingExpectation: {
      mappingVersion: 0,
      formalAssetId: null,
      targetVersion: null,
    },
    expectedMappingExpectationHash: hash("3"),
    profile: {
      targetMode: "synthetic",
      environmentCode: "disposable",
      snapshotHash: hash("4"),
    },
    expectedProfileSnapshotHash: hash("4"),
  };
}

export function toolAssetExecutionDetail(
  state: ToolAssetExecutionDetail["request"]["state"] = "synthetic_verified",
): ToolAssetExecutionDetail {
  const context = toolAssetExecutionContext();
  const hasResult = !["validated_mock", "queued", "processing"].includes(state);
  const authority =
    state === "succeeded"
      ? "authoritative_sandbox"
      : state === "synthetic_verified"
        ? "synthetic"
        : "none";
  const fieldState =
    state === "succeeded"
      ? "succeeded_authoritative"
      : state === "synthetic_verified"
        ? "synthetic_verified"
        : state === "uncertain_after_timeout"
          ? "uncertain_after_timeout"
          : state === "partially_succeeded"
            ? "failed_retryable"
            : "failed_final";
  return {
    requestGlobalId: toolAssetExecutionRequestId,
    request: {
      globalId: toolAssetExecutionRequestId,
      operation: context.operation,
      state,
      source: context.source,
      approval: context.approval,
      mappingExpectation: context.mappingExpectation,
      profile: context.profile,
      optimisticVersion: 2,
      payloadHash: hash("5"),
      createdAt: "2026-08-24T01:00:00Z",
    },
    dispatchAllowed: false,
    outboxEventId: "79000000-0000-4000-8000-000000000004",
    targetIdempotencyKeyHash: hash("6"),
    semanticEffectHash: hash("7"),
    resultGlobalId: hasResult ? toolAssetExecutionResultId : null,
    attempts: hasResult
      ? [
          {
            globalId: toolAssetExecutionAttemptId,
            attemptNumber: 1,
            state:
              state === "synthetic_verified"
                ? "synthetic_verified"
                : "observed_failure",
            adapterBoundaryCrossed: true,
            transportDisposition: "observed",
            faultKind:
              state === "synthetic_verified" ? null : "business_validation",
            reconciliationRequired: state === "uncertain_after_timeout",
            safeErrorCode:
              state === "synthetic_verified"
                ? null
                : "TOOL_ASSET_FIELD_RESULT_INCOMPLETE",
            startedAt: "2026-08-24T01:01:00Z",
            finishedAt: "2026-08-24T01:02:00Z",
          },
        ]
      : [],
    result: hasResult
      ? {
          globalId: toolAssetExecutionResultId,
          attemptGlobalId: toolAssetExecutionAttemptId,
          attemptNumber: 1,
          operation: context.operation,
          state,
          authority,
          responseAuthenticated: state === "succeeded",
          faultKind:
            state === "synthetic_verified" ? "none" : "business_validation",
          observedAt: "2026-08-24T01:02:00Z",
          formalAssetId: null,
          targetVersion: null,
        }
      : null,
    fieldResults: hasResult
      ? [
          "tooling_master_title",
          "physical_set_serial",
          "tooling_requirement_kind",
          "source_tooling_revision",
          "acceptance_evidence_reference",
        ].map((fieldCode) => ({
          fieldCode,
          state: fieldState,
          authority,
          responseAuthenticated: state === "succeeded",
          faultKind:
            state === "synthetic_verified" ? "none" : "business_validation",
          observedAt: "2026-08-24T01:02:00Z",
        }))
      : [],
    mappingObservation: hasResult
      ? {
          disposition: state === "succeeded" ? "advance" : "non_authoritative",
          authority,
          responseAuthenticated: state === "succeeded",
          observedAt: "2026-08-24T01:02:00Z",
          previousFormalAssetId: null,
          previousTargetVersion: null,
          observedFormalAssetId: null,
          observedTargetVersion: null,
        }
      : null,
    currentMapping:
      state === "succeeded"
        ? {
            mappingVersion: 2,
            formalAssetId: "ASSET-00042",
            targetVersion: "asset-v7",
            observationHash: hash("8"),
            updatedAt: "2026-08-24T01:02:00Z",
          }
        : null,
    permissions: { canView: true, canCreate: true, canUpdate: false },
  };
}

export function toolAssetExecutionCollection(
  detail = toolAssetExecutionDetail(),
): ToolAssetExecutionCollection {
  const context = toolAssetExecutionContext();
  const summary = {
    requestGlobalId: detail.requestGlobalId,
    request: detail.request,
    dispatchAllowed: detail.dispatchAllowed,
    outboxEventId: detail.outboxEventId,
    targetIdempotencyKeyHash: detail.targetIdempotencyKeyHash,
    semanticEffectHash: detail.semanticEffectHash,
    resultGlobalId: detail.resultGlobalId,
  };
  return {
    projectGlobalId: ids.project,
    toolingMasterGlobalId: ids.master,
    toolingSetGlobalId: ids.set,
    permissions: detail.permissions,
    businessApproval: context.approval,
    executionProfile: context.profile,
    commandContexts: { create_tool_asset: context },
    items: [summary],
  };
}
