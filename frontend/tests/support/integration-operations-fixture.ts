import type {
  IntegrationOperationCollection,
  IntegrationOperationDetail,
  IntegrationOperationItem,
  IntegrationOperationKind,
  IntegrationOperationState,
} from "../../src/api/integration-operations-data-source";

export const integrationOperationsProjectId =
  "11111111-1111-4111-8111-111111111111";

const kinds: readonly IntegrationOperationKind[] = [
  "receive_project_submission",
  "publish_item",
  "publish_mbom",
  "create_tool_asset",
  "update_tool_asset",
];
const states: readonly IntegrationOperationState[] = [
  "queued",
  "processing",
  "succeeded",
  "failed_retryable",
  "failed_final",
  "uncertain",
  "partial",
  "conflict",
  "quarantined",
  "unavailable",
];
const dlq = new Set<IntegrationOperationState>([
  "failed_retryable",
  "failed_final",
  "uncertain",
  "partial",
  "conflict",
  "quarantined",
]);

function id(index: number, offset = 0): string {
  return `10000000-0000-4000-8000-${String(index + offset).padStart(12, "0")}`;
}

function hash(character: string): string {
  return character.repeat(64);
}

function replayReason(state: IntegrationOperationState) {
  if (state === "failed_retryable") return "eligible" as const;
  if (state === "uncertain") return "uncertain_boundary" as const;
  if (state === "partial") return "partial_result" as const;
  return "state_not_retryable" as const;
}

function fault(state: IntegrationOperationState) {
  switch (state) {
    case "failed_retryable":
      return "retryable_before_uncertain_boundary" as const;
    case "failed_final":
      return "final_business_failure" as const;
    case "uncertain":
      return "uncertain_after_boundary" as const;
    case "partial":
      return "partial_result" as const;
    case "conflict":
      return "identity_conflict" as const;
    case "quarantined":
      return "authenticity_quarantine" as const;
    case "unavailable":
      return "target_unavailable" as const;
    default:
      return "none" as const;
  }
}

export function integrationOperationItem(
  state: IntegrationOperationState,
  index = states.indexOf(state) + 1,
): IntegrationOperationItem {
  const reconciliationRequired = state === "uncertain" || state === "partial";
  return {
    tenantId: "tenant-a",
    projectGlobalId: integrationOperationsProjectId,
    operationKind: kinds[(index - 1) % kinds.length] ?? "publish_item",
    operationGlobalId: id(index),
    sourceGlobalId: id(index, 100),
    operationVersion: index,
    rawState: `owner_state_${String(index)}`,
    sharedState: state,
    sourceSnapshotHash: hash("a"),
    targetIdempotencyKeyHash: hash("b"),
    logicalDlq: dlq.has(state),
    faultClass: fault(state),
    replayEligible: state === "failed_retryable",
    replayEligibilityReason: replayReason(state),
    reconciliationRequired,
    updatedAt: `2026-08-28T${String(index % 10).padStart(2, "0")}:00:00Z`,
  };
}

export function integrationOperationItems(): readonly IntegrationOperationItem[] {
  return states.map((state, index) =>
    integrationOperationItem(state, index + 1),
  );
}

export function integrationOperationCollection(
  options: {
    act?: boolean;
    items?: readonly IntegrationOperationItem[];
    view?: boolean;
  } = {},
): IntegrationOperationCollection {
  return {
    projectGlobalId: integrationOperationsProjectId,
    permissions: { view: options.view ?? true, act: options.act ?? true },
    items: options.items ?? integrationOperationItems(),
    nextCursor: null,
  };
}

export function integrationOperationDetail(
  item: IntegrationOperationItem = integrationOperationItem(
    "failed_retryable",
    4,
  ),
): IntegrationOperationDetail {
  return {
    projectGlobalId: integrationOperationsProjectId,
    permissions: { view: true, act: true },
    operation: {
      ...item,
      attempts: [
        {
          attemptGlobalId: id(401),
          attemptNumber: 1,
          state: "failed_retryable",
          adapterBoundaryCrossed: false,
          reconciliationRequired: false,
          safeErrorCode: "TARGET_TEMPORARILY_UNAVAILABLE",
          startedAt: "2026-08-28T03:00:00Z",
          finishedAt: "2026-08-28T03:00:10Z",
        },
      ],
      results: [
        {
          resultGlobalId: id(501),
          attemptGlobalId: id(401),
          attemptNumber: 1,
          state: "failed_retryable",
          authority: "none",
          responseAuthenticated: false,
          faultKind: "target_unavailable",
          observedAt: "2026-08-28T03:00:10Z",
        },
      ],
      actions: [],
    },
  };
}
