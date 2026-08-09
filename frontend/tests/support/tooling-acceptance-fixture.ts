import {
  TOOL_ASSET_MOCK_ACKNOWLEDGEMENT,
  toolingAcceptanceCategories,
  type CreateToolAssetRequestCommand,
  type CreateToolingAcceptanceEvidenceRevisionCommand,
  type ToolAssetRequestCollectionViewModel,
  type ToolAssetRequestViewModel,
  type ToolingAcceptanceAssetContextViewModel,
  type ToolingAcceptanceEvidenceRevisionViewModel,
} from "../../src/api/tooling-data-source";

export const toolingAcceptanceIds = {
  acceptance: "11111111-1111-4111-8111-111111111111",
  acceptanceRevision: "22222222-2222-4222-8222-222222222222",
  binding: "33333333-3333-4333-8333-333333333333",
  master: "44444444-4444-4444-8444-444444444444",
  project: "55555555-5555-4555-8555-555555555555",
  request: "66666666-6666-4666-8666-666666666666",
  revision: "77777777-7777-4777-8777-777777777777",
  set: "88888888-8888-4888-8888-888888888888",
} as const;

export const toolingAcceptanceHash = (value: string): string =>
  value.repeat(64);

export function acceptanceRevision(): ToolingAcceptanceEvidenceRevisionViewModel {
  return {
    acceptanceGlobalId: toolingAcceptanceIds.acceptance,
    acceptanceVersion: 1,
    assetActions: [],
    businessApproval: {
      reasonCode: "tooling_acceptance_policy_unavailable",
      state: "unavailable",
    },
    categoryCoverage: toolingAcceptanceCategories.map((category) => ({
      category,
      itemCount: 1,
      missingCount: 1,
      notApplicableCount: 0,
      recordedCount: 0,
    })),
    checklist: toolingAcceptanceCategories.map((category, index) => ({
      category,
      disposition: "evidence_missing",
      evidence: [],
      globalId: `${(index + 1).toString(16).padStart(8, "0")}-aaaa-4aaa-8aaa-aaaaaaaaaaaa`,
      note: null,
      requirementKey: `acceptance.${category}`,
      requirementStatement: `${category} acceptance requirement`,
      responsibleMember: null,
    })),
    createdAt: "2026-08-08T12:00:00Z",
    createdByUserId: "tooling.engineer@example.invalid",
    globalId: toolingAcceptanceIds.acceptanceRevision,
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    projectGlobalId: toolingAcceptanceIds.project,
    reason: "Initial controlled acceptance evidence",
    repairs: [],
    requestId: toolingAcceptanceIds.request,
    schemaVersion: 1,
    setRevisionBindingGlobalId: toolingAcceptanceIds.binding,
    setRevisionBindingSnapshotHash: toolingAcceptanceHash("b"),
    snapshotHash: toolingAcceptanceHash("c"),
    spareRecommendations: [],
    tenantId: "tenant.test",
    toolingMasterGlobalId: toolingAcceptanceIds.master,
    toolingMasterSnapshotHash: toolingAcceptanceHash("d"),
    toolingRequirementKind: "copy_or_additional_set",
    toolingRevisionGlobalId: toolingAcceptanceIds.revision,
    toolingRevisionNumber: 1,
    toolingRevisionSnapshotHash: toolingAcceptanceHash("e"),
    toolingSetGlobalId: toolingAcceptanceIds.set,
    toolingSetSnapshotHash: toolingAcceptanceHash("f"),
    traceId: "trace-tooling-acceptance",
    versionKeyHash: toolingAcceptanceHash("1"),
  };
}

export function acceptanceCommand(): CreateToolingAcceptanceEvidenceRevisionCommand {
  const acceptance = acceptanceRevision();
  return {
    assetActions: [],
    checklist: acceptance.checklist.map((item) => ({
      category: item.category,
      disposition: item.disposition,
      evidence: [],
      note: item.note,
      requirementKey: item.requirementKey,
      requirementStatement: item.requirementStatement,
      responsibleMember: null,
    })),
    reason: "Initial controlled acceptance evidence",
    repairs: [],
    setRevisionBindingGlobalId: acceptance.setRevisionBindingGlobalId,
    setRevisionBindingSnapshotHash: acceptance.setRevisionBindingSnapshotHash,
    spareRecommendations: [],
    toolingRevisionGlobalId: acceptance.toolingRevisionGlobalId,
    toolingRevisionNumber: acceptance.toolingRevisionNumber,
    toolingRevisionSnapshotHash: acceptance.toolingRevisionSnapshotHash,
    toolingSetGlobalId: acceptance.toolingSetGlobalId,
    toolingSetSnapshotHash: acceptance.toolingSetSnapshotHash,
  };
}

export function assetRequest(): ToolAssetRequestViewModel {
  const acceptance = acceptanceRevision();
  return {
    actorUserId: "tooling.engineer@example.invalid",
    apiVersion: "npi.tooling-asset.v1",
    businessApprovalState: "unavailable",
    createdAt: "2026-08-08T12:05:00Z",
    dispatchState: "prohibited",
    formalAssetMapping: {
      editableIn: "ERPNEXT",
      mappingCardinality: "zero_or_one_per_physical_set",
      reasonCode: "erp_asset_mapping_unavailable",
      sourceSystem: "ERPNEXT",
      state: "unavailable",
    },
    globalId: toolingAcceptanceIds.request,
    idempotencyKeyHash: toolingAcceptanceHash("2"),
    inputValidationState: "validated_mock",
    operation: "create_or_update_tool_asset",
    payloadHash: toolingAcceptanceHash("3"),
    requestId: toolingAcceptanceIds.request,
    requestInput: {
      acceptanceRevisionGlobalId: acceptance.globalId,
      acceptanceSnapshotHash: acceptance.snapshotHash,
      acceptanceVersion: acceptance.acceptanceVersion,
      ownedFieldsManifest: [
        "tooling_master_title",
        "physical_set_serial",
        "tooling_requirement_kind",
        "source_tooling_revision",
        "acceptance_evidence_reference",
      ],
      projectGlobalId: toolingAcceptanceIds.project,
      schemaVersion: 1,
      setRevisionBindingGlobalId: toolingAcceptanceIds.binding,
      setRevisionBindingSnapshotHash: toolingAcceptanceHash("b"),
      toolingMasterGlobalId: toolingAcceptanceIds.master,
      toolingMasterSnapshotHash: toolingAcceptanceHash("d"),
      toolingMasterTitle: "Customer tool family A",
      toolingRequirementKind: "copy_or_additional_set",
      toolingRevisionGlobalId: toolingAcceptanceIds.revision,
      toolingRevisionLabel: "R1",
      toolingRevisionNumber: 1,
      toolingRevisionSnapshotHash: toolingAcceptanceHash("e"),
      toolingSetGlobalId: toolingAcceptanceIds.set,
      toolingSetPhysicalSerial: "SET-001",
      toolingSetSnapshotHash: toolingAcceptanceHash("f"),
    },
    requestInputHash: toolingAcceptanceHash("4"),
    requestState: "draft",
    snapshotHash: toolingAcceptanceHash("5"),
    targetMode: "mock",
    targetResult: {
      reasonCode: "phase_6_dispatch_prohibited",
      state: "not_requested",
    },
    targetResultState: "not_requested",
    tenantId: "tenant.test",
    traceId: "trace-tooling-asset-request",
  };
}

export function assetRequestCommand(): CreateToolAssetRequestCommand {
  const acceptance = acceptanceRevision();
  return {
    acceptanceRevisionGlobalId: acceptance.globalId,
    acceptanceSnapshotHash: acceptance.snapshotHash,
    acceptanceVersion: acceptance.acceptanceVersion,
    acknowledgement: TOOL_ASSET_MOCK_ACKNOWLEDGEMENT,
    expectedBindingSnapshotHash: acceptance.setRevisionBindingSnapshotHash,
    expectedToolingMasterSnapshotHash: acceptance.toolingMasterSnapshotHash,
    expectedToolingRevisionNumber: acceptance.toolingRevisionNumber,
    expectedToolingRevisionSnapshotHash: acceptance.toolingRevisionSnapshotHash,
    expectedToolingSetSnapshotHash: acceptance.toolingSetSnapshotHash,
    targetMode: "mock",
  };
}

export function acceptanceContext(
  overrides: Partial<ToolingAcceptanceAssetContextViewModel> = {},
): ToolingAcceptanceAssetContextViewModel {
  return {
    acceptanceRevisions: [acceptanceRevision()],
    assetProjection: {
      editableIn: "ERPNEXT",
      mappingCardinality: "zero_or_one_per_physical_set",
      reasonCode: "erp_asset_projection_unavailable",
      sourceSystem: "ERPNEXT",
      state: "unavailable",
    },
    assetRequests: [],
    businessApproval: {
      reasonCode: "tooling_acceptance_policy_unavailable",
      state: "unavailable",
    },
    permissions: {
      approveAcceptance: false,
      dispatchAssetRequest: false,
      editErpProjection: false,
      prepareMockAssetRequest: true,
      recordEvidence: true,
      view: true,
    },
    projectGlobalId: toolingAcceptanceIds.project,
    toolingMasterGlobalId: toolingAcceptanceIds.master,
    ...overrides,
  };
}

export function assetRequestCollection(): ToolAssetRequestCollectionViewModel {
  return {
    items: [assetRequest()],
    projectGlobalId: toolingAcceptanceIds.project,
    toolingMasterGlobalId: toolingAcceptanceIds.master,
  };
}
