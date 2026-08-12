import type {
  ReadinessInstanceRevision,
  ReadinessItemSnapshot,
  ReadinessPermissions,
  ReadinessTemplateVersion,
  ReadinessWorkspace,
} from "../../src/api/readiness-data-source";

export const readinessIds = {
  designReleaseItem: "b0c315d1-06f1-5db9-980b-3a9f85870b5b",
  designReleaseSource: "70000000-0000-4000-8000-000000000002",
  gateFive: "70000000-0000-4000-8000-000000000003",
  gateSix: "70000000-0000-4000-8000-000000000004",
  initializationRequest: "70000000-0000-4000-8000-000000000015",
  initializationRevision: "70000000-0000-4000-8000-000000000014",
  instance: "70000000-0000-4000-8000-000000000005",
  project: "11111111-1111-4111-8111-111111111111",
  qualityMember: "61000000-0000-4000-8000-000000000002",
  requestOne: "70000000-0000-4000-8000-000000000006",
  requestTwo: "70000000-0000-4000-8000-000000000007",
  requestThree: "70000000-0000-4000-8000-00000000000f",
  revisionOne: "70000000-0000-4000-8000-000000000008",
  revisionTwo: "70000000-0000-4000-8000-000000000009",
  revisionThree: "70000000-0000-4000-8000-000000000010",
  supplierItem: "797f6415-5d7f-5994-8e05-06ddc04bb22d",
  template: "70000000-0000-4000-8000-000000000011",
  templateRevision: "1597fc12-d98b-56cf-a66c-c210b59c7bea",
  trialConclusionItem: "27ab2a06-1c15-51b7-ab55-6efe070989c0",
  trialConclusionSource: "70000000-0000-4000-8000-00000000000d",
  workItemSource: "70000000-0000-4000-8000-00000000000e",
} as const;

export function readinessPublishedTemplate(): ReadinessTemplateVersion {
  return {
    applicability: {
      customerReferenceKeys: [],
      industryKeys: ["automotive"],
      projectTypes: ["new_tool"],
    },
    categories: [{ key: "engineering", title: "Engineering readiness" }],
    changedAt: "2026-08-11T10:00:00Z",
    changedByUserId: "system.manager@example.invalid",
    globalId: "d3b3c792-a812-503a-82a0-91cecd72d3f9",
    items: [
      {
        applicability: {
          customerReferenceKeys: [],
          industryKeys: ["automotive"],
          projectTypes: [],
        },
        blockingLevel: "P0",
        categoryKey: "engineering",
        completionRule: "exact_evidence",
        evidenceRequirements: [
          {
            acceptedSourceKinds: ["released_document"],
            key: "released_design",
            minimumCount: 1,
            unavailableBlocks: true,
          },
        ],
        gateKey: "G5",
        key: "design_release",
        required: true,
        title: "Released design baseline",
        weight: 100,
      },
    ],
    optimisticVersion: 2,
    publicationState: "published",
    requestId: "71000000-0000-4000-8000-000000000003",
    snapshotHash:
      "bc77a5eb394a486eb41447c544f0d857ae58371357723a54e6162b9273eed034",
    templateCode: "AUTO-RDY",
    templateGlobalId: "71000000-0000-4000-8000-000000000002",
    templateVersion: 1,
    title: "Automotive readiness",
    traceId: "trace-readiness-template",
  };
}

const projectApplicability = {
  customerReferenceKeys: [],
  industryKeys: ["automotive"],
  projectTypes: ["new_tool"],
} as const;

const categories = [
  { key: "engineering", title: "Engineering release" },
  { key: "industrialization", title: "Industrialization evidence" },
] as const;

const gateFive = {
  gateKey: "G5",
  globalId: readinessIds.gateFive,
  optimisticVersion: 2,
  snapshotHash: "5".repeat(64),
} as const;

const gateSix = {
  gateKey: "G6",
  globalId: readinessIds.gateSix,
  optimisticVersion: 3,
  snapshotHash: "6".repeat(64),
} as const;

const owner = {
  globalId: readinessIds.qualityMember,
  optimisticVersion: 1,
  userId: "quality.lead@example.invalid",
} as const;

function designReleaseItem(): ReadinessItemSnapshot {
  return {
    applicable: true,
    confirmationValue: null,
    definition: {
      applicability: projectApplicability,
      blockingLevel: "P1",
      categoryKey: "engineering",
      completionRule: "exact_evidence",
      evidenceRequirements: [
        {
          acceptedSourceKinds: ["released_document"],
          key: "released_design",
          minimumCount: 1,
          unavailableBlocks: true,
        },
      ],
      gateKey: "G5",
      key: "design_release",
      required: true,
      title: "Released design baseline",
      weight: 70,
    },
    dueDate: "2026-08-18",
    gate: gateFive,
    globalId: readinessIds.designReleaseItem,
    itemVersion: 2,
    owner,
    sources: [
      {
        globalId: readinessIds.designReleaseSource,
        kind: "released_document",
        reasonCode: null,
        requirementKey: "released_design",
        snapshotHash: "a".repeat(64),
        sourceVersion: 4,
        state: "satisfied",
      },
    ],
    state: "complete",
  };
}

function trialConclusionItem(): ReadinessItemSnapshot {
  return {
    applicable: true,
    confirmationValue: null,
    definition: {
      applicability: projectApplicability,
      blockingLevel: "P1",
      categoryKey: "industrialization",
      completionRule: "exact_source_result",
      evidenceRequirements: [
        {
          acceptedSourceKinds: ["trial_conclusion"],
          key: "approved_trial_conclusion",
          minimumCount: 1,
          unavailableBlocks: true,
        },
      ],
      gateKey: "G6",
      key: "trial_conclusion",
      required: true,
      title: "Approved trial conclusion",
      weight: 29,
    },
    dueDate: "2026-08-20",
    gate: gateSix,
    globalId: readinessIds.trialConclusionItem,
    itemVersion: 2,
    owner,
    sources: [
      {
        globalId: readinessIds.trialConclusionSource,
        kind: "trial_conclusion",
        reasonCode: null,
        requirementKey: "approved_trial_conclusion",
        snapshotHash: "b".repeat(64),
        sourceVersion: 2,
        state: "satisfied",
      },
    ],
    state: "complete",
  };
}

function supplierEvidenceItem(): ReadinessItemSnapshot {
  return {
    applicable: true,
    confirmationValue: null,
    definition: {
      applicability: projectApplicability,
      blockingLevel: "P0",
      categoryKey: "industrialization",
      completionRule: "exact_source_result",
      evidenceRequirements: [
        {
          acceptedSourceKinds: ["erp_supplier_execution"],
          key: "formal_supplier_execution",
          minimumCount: 1,
          unavailableBlocks: true,
        },
      ],
      gateKey: "G6",
      key: "supplier_execution",
      required: true,
      title: "Formal supplier execution result",
      weight: 1,
    },
    dueDate: "2026-08-22",
    gate: gateSix,
    globalId: readinessIds.supplierItem,
    itemVersion: 1,
    owner,
    sources: [
      {
        globalId: null,
        kind: "erp_supplier_execution",
        reasonCode: "erp_supplier_execution_provider_unavailable",
        requirementKey: "formal_supplier_execution",
        snapshotHash: null,
        sourceVersion: null,
        state: "unavailable",
      },
    ],
    state: "not_started",
  };
}

function revision(
  values: Pick<
    ReadinessInstanceRevision,
    | "createdAt"
    | "createdByUserId"
    | "evaluation"
    | "globalId"
    | "instanceVersion"
    | "items"
    | "predecessorGlobalId"
    | "predecessorSnapshotHash"
    | "requestId"
    | "snapshotHash"
    | "traceId"
    | "versionKeyHash"
  >,
): ReadinessInstanceRevision {
  return {
    categories,
    instanceGlobalId: readinessIds.instance,
    project: {
      customerReferenceKeys: [],
      globalId: readinessIds.project,
      industryKey: "automotive",
      optimisticVersion: 4,
      projectType: "new_tool",
      snapshotHash: "4".repeat(64),
    },
    templateRevision: {
      globalId: readinessIds.templateRevision,
      snapshotHash:
        "859ff1d8de0cdee2394e06d33bf927062703f0030aede1e43fa6c631c1e2ba5b",
      version: 1,
    },
    tenantId: "npi-one-test",
    ...values,
  };
}

export function readinessRevisionOne(): ReadinessInstanceRevision {
  const engineering = designReleaseItem();
  const trial = { ...trialConclusionItem(), state: "in_progress" as const };
  const supplier = supplierEvidenceItem();
  return revision({
    createdAt: "2026-08-11T08:00:00Z",
    createdByUserId: "quality.lead@example.invalid",
    evaluation: {
      blockers: [
        {
          code: "incomplete_p0",
          gate: gateSix,
          itemGlobalId: supplier.globalId,
          itemKey: supplier.definition.key,
        },
        {
          code: "required_source_unavailable",
          gate: gateSix,
          itemGlobalId: supplier.globalId,
          itemKey: supplier.definition.key,
        },
      ],
      categoryScores: [
        {
          applicableWeight: 70,
          basisPoints: 10_000,
          categoryKey: "engineering",
          earnedWeight: 70,
          state: "scored",
        },
        {
          applicableWeight: 30,
          basisPoints: 0,
          categoryKey: "industrialization",
          earnedWeight: 0,
          state: "scored",
        },
      ],
      formulaVersion: "readiness-score.v1",
      ready: false,
      totalScore: {
        applicableWeight: 100,
        basisPoints: 7000,
        categoryKey: null,
        earnedWeight: 70,
        state: "scored",
      },
    },
    globalId: readinessIds.revisionOne,
    instanceVersion: 1,
    items: [engineering, trial, supplier],
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    requestId: readinessIds.requestOne,
    snapshotHash:
      "dabee9a324c30241971cccd4ce8e017fa8d2af8f70b1d40807be2d8ddc7f1f83",
    traceId: "trace-readiness-revision-one",
    versionKeyHash:
      "f30bbd4afd43b036e7315d6a9c4a1f4a3175c66125b82e712d420012a2a46c1f",
  });
}

export function readinessInitializationRevision(): ReadinessInstanceRevision {
  const engineering = {
    ...designReleaseItem(),
    itemVersion: 1,
    sources: [],
    state: "not_started" as const,
  };
  const trial = {
    ...trialConclusionItem(),
    itemVersion: 1,
    sources: [],
    state: "not_started" as const,
  };
  const supplier = { ...supplierEvidenceItem(), sources: [] };
  return revision({
    createdAt: "2026-08-11T07:50:00Z",
    createdByUserId: "quality.lead@example.invalid",
    evaluation: {
      blockers: [
        {
          code: "incomplete_p0",
          gate: gateSix,
          itemGlobalId: supplier.globalId,
          itemKey: supplier.definition.key,
        },
      ],
      categoryScores: [
        {
          applicableWeight: 70,
          basisPoints: 0,
          categoryKey: "engineering",
          earnedWeight: 0,
          state: "scored",
        },
        {
          applicableWeight: 30,
          basisPoints: 0,
          categoryKey: "industrialization",
          earnedWeight: 0,
          state: "scored",
        },
      ],
      formulaVersion: "readiness-score.v1",
      ready: false,
      totalScore: {
        applicableWeight: 100,
        basisPoints: 0,
        categoryKey: null,
        earnedWeight: 0,
        state: "scored",
      },
    },
    globalId: readinessIds.initializationRevision,
    instanceVersion: 1,
    items: [engineering, trial, supplier],
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    requestId: readinessIds.initializationRequest,
    snapshotHash:
      "c63987faa72071542f64e2686edf40977d6aff25573256add143f5e46f09f04b",
    traceId: "trace-readiness-initialization",
    versionKeyHash:
      "f30bbd4afd43b036e7315d6a9c4a1f4a3175c66125b82e712d420012a2a46c1f",
  });
}

export function readinessRevisionTwo(): ReadinessInstanceRevision {
  const engineering = designReleaseItem();
  const trial = { ...trialConclusionItem(), itemVersion: 3 };
  const supplier = supplierEvidenceItem();
  return revision({
    createdAt: "2026-08-11T09:00:00Z",
    createdByUserId: "quality.lead@example.invalid",
    evaluation: {
      blockers: [
        {
          code: "incomplete_p0",
          gate: gateSix,
          itemGlobalId: supplier.globalId,
          itemKey: supplier.definition.key,
        },
        {
          code: "required_source_unavailable",
          gate: gateSix,
          itemGlobalId: supplier.globalId,
          itemKey: supplier.definition.key,
        },
      ],
      categoryScores: [
        {
          applicableWeight: 70,
          basisPoints: 10_000,
          categoryKey: "engineering",
          earnedWeight: 70,
          state: "scored",
        },
        {
          applicableWeight: 30,
          basisPoints: 9667,
          categoryKey: "industrialization",
          earnedWeight: 29,
          state: "scored",
        },
      ],
      formulaVersion: "readiness-score.v1",
      ready: false,
      totalScore: {
        applicableWeight: 100,
        basisPoints: 9900,
        categoryKey: null,
        earnedWeight: 99,
        state: "scored",
      },
    },
    globalId: readinessIds.revisionTwo,
    instanceVersion: 2,
    items: [engineering, trial, supplier],
    predecessorGlobalId: readinessIds.revisionOne,
    predecessorSnapshotHash:
      "dabee9a324c30241971cccd4ce8e017fa8d2af8f70b1d40807be2d8ddc7f1f83",
    requestId: readinessIds.requestTwo,
    snapshotHash:
      "0780e831695a9ee52b688438079bb6a233a23a391b51d7c4f03ca284905299a6",
    traceId: "trace-readiness-revision-two",
    versionKeyHash:
      "00a2b466790bbea4f222ad5bf0f73f86afbc32723a6f05a49c2042705a6e5587",
  });
}

export function readinessRevisionThree(): ReadinessInstanceRevision {
  const engineering = designReleaseItem();
  const trial = { ...trialConclusionItem(), itemVersion: 3 };
  const supplier = {
    ...supplierEvidenceItem(),
    itemVersion: 2,
    state: "in_progress" as const,
  };
  return revision({
    createdAt: "2026-08-11T09:30:00Z",
    createdByUserId: "quality.lead@example.invalid",
    evaluation: {
      blockers: [
        {
          code: "incomplete_p0",
          gate: gateSix,
          itemGlobalId: supplier.globalId,
          itemKey: supplier.definition.key,
        },
        {
          code: "required_source_unavailable",
          gate: gateSix,
          itemGlobalId: supplier.globalId,
          itemKey: supplier.definition.key,
        },
      ],
      categoryScores: [
        {
          applicableWeight: 70,
          basisPoints: 10_000,
          categoryKey: "engineering",
          earnedWeight: 70,
          state: "scored",
        },
        {
          applicableWeight: 30,
          basisPoints: 9667,
          categoryKey: "industrialization",
          earnedWeight: 29,
          state: "scored",
        },
      ],
      formulaVersion: "readiness-score.v1",
      ready: false,
      totalScore: {
        applicableWeight: 100,
        basisPoints: 9900,
        categoryKey: null,
        earnedWeight: 99,
        state: "scored",
      },
    },
    globalId: readinessIds.revisionThree,
    instanceVersion: 3,
    items: [engineering, trial, supplier],
    predecessorGlobalId: readinessIds.revisionTwo,
    predecessorSnapshotHash:
      "0780e831695a9ee52b688438079bb6a233a23a391b51d7c4f03ca284905299a6",
    requestId: readinessIds.requestThree,
    snapshotHash:
      "b1dd550e027d35f9eb3df30b8691dc4015c706f88e3bab65197890d77fe49505",
    traceId: "trace-readiness-revision-three",
    versionKeyHash:
      "d88180aabd2ca6d0e199b1d75190a38b37275613d3c6bde840d4b3a916bbeaf8",
  });
}

export function readinessWorkspace(
  overrides: Partial<ReadinessWorkspace> = {},
): ReadinessWorkspace {
  const first = readinessRevisionOne();
  const current = readinessRevisionTwo();
  return {
    currentRevision: current,
    permissions: {
      canInitialize: false,
      canManageTemplates: false,
      canRevise: true,
    },
    projectGlobalId: readinessIds.project,
    revisions: [first, current],
    sourceOptions: [
      {
        globalId: readinessIds.workItemSource,
        kind: "domain_work_item",
        label: "Resolve supplier process capability",
        snapshotHash: "9".repeat(64),
        sourceVersion: 3,
        stateLabelSource: "Open",
        stateTerminal: false,
      },
    ],
    unavailableProjections: [
      {
        kind: "erp_hr_qualification",
        reasonCode: "erp_hr_qualification_provider_unavailable",
        state: "unavailable",
      },
      {
        kind: "erp_material_specification",
        reasonCode: "erp_material_specification_provider_unavailable",
        state: "unavailable",
      },
      {
        kind: "erp_quality_result",
        reasonCode: "erp_quality_result_provider_unavailable",
        state: "unavailable",
      },
      {
        kind: "erp_run_at_rate",
        reasonCode: "erp_run_at_rate_provider_unavailable",
        state: "unavailable",
      },
      {
        kind: "erp_supplier_execution",
        reasonCode: "erp_supplier_execution_provider_unavailable",
        state: "unavailable",
      },
    ],
    ...overrides,
  };
}

export function readinessEmptyWorkspace(
  permissions: ReadinessPermissions = {
    canInitialize: false,
    canManageTemplates: false,
    canRevise: false,
  },
): ReadinessWorkspace {
  return readinessWorkspace({
    currentRevision: null,
    permissions,
    revisions: [],
    sourceOptions: [],
  });
}

export function readinessInitializationWorkspace(): ReadinessWorkspace {
  const current = readinessInitializationRevision();
  return readinessWorkspace({
    currentRevision: current,
    revisions: [current],
  });
}

export function readinessRevisedWorkspace(): ReadinessWorkspace {
  const first = readinessRevisionOne();
  const second = readinessRevisionTwo();
  const current = readinessRevisionThree();
  return readinessWorkspace({
    currentRevision: current,
    revisions: [first, second, current],
  });
}
