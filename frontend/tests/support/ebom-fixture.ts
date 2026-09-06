import type {
  EngineeringBomCommandViewModel,
  EngineeringBomComparisonViewModel,
  EngineeringBomDetailViewModel,
  EngineeringBomListViewModel,
  EngineeringBomRevisionViewModel,
} from "../../src/api/ebom-data-source";

export const ebomProjectId = "75000000-0000-4000-8000-000000000001";
export const ebomId = "75000000-0000-4000-8000-000000000002";
export const ebomRevisionOneId = "75000000-0000-4000-8000-000000000003";
export const ebomRevisionTwoId = "75000000-0000-4000-8000-000000000004";
export const ebomPolicyId = "75000000-0000-4000-8000-000000000005";
const lineOneId = "75000000-0000-4000-8000-000000000006";
const lineTwoId = "75000000-0000-4000-8000-000000000007";
const eventSubmitId = "75000000-0000-4000-8000-000000000008";
const eventApproveId = "75000000-0000-4000-8000-000000000009";
const eventReleaseId = "75000000-0000-4000-8000-000000000010";
const hashA = "a".repeat(64);
const hashB = "b".repeat(64);
const hashC = "c".repeat(64);
const syntheticEngineeringBomBusinessId = "synthetic.ebom.001";

const project = {
  globalId: ebomProjectId,
  businessCode: "NPI-2026-075",
  title: "Synthetic EBOM Project",
  lifecycleState: "active",
  optimisticVersion: 4,
} as const;

const policy = {
  globalId: ebomPolicyId,
  version: 1,
  snapshotHash: hashA,
  key: "synthetic.ebom.policy",
  title: "Synthetic EBOM policy",
  syntheticNamespace: "synthetic_p504",
  quantityScale: 3,
  maximumNodes: 20,
  engineeringUoms: ["EA", "MM"],
  attributeKeys: ["material", "finish"],
} as const;

const summary = {
  globalId: ebomId,
  engineeringBomKey: syntheticEngineeringBomBusinessId,
  title: "Synthetic assembly EBOM",
  policy: {
    globalId: policy.globalId,
    version: policy.version,
    snapshotHash: policy.snapshotHash,
  },
  optimisticVersion: 2,
  latestRevision: {
    globalId: ebomRevisionTwoId,
    revisionNumber: 2,
    snapshotHash: hashC,
  },
} as const;

const lineOne = {
  globalId: lineOneId,
  lineKey: "root",
  parentLineKey: null,
  engineeringItemId: "ENG-SYN-001",
  description: "Synthetic housing",
  quantity: "1.000",
  engineeringUom: "EA",
  alternateForLineKey: null,
  alternateGroupKey: null,
  effectivityStart: "2026-08-01",
  effectivityEnd: null,
  attributes: { material: "synthetic-resin" },
} as const;

const lineTwo = {
  ...lineOne,
  globalId: lineTwoId,
  quantity: "2.000",
} as const;

const revisionOne: EngineeringBomRevisionViewModel = {
  globalId: ebomRevisionOneId,
  revisionNumber: 1,
  snapshotHash: hashB,
  predecessorRevisionId: null,
  predecessorSnapshotHash: null,
  reason: "Initial synthetic EBOM",
  effectivityNote: "Synthetic validation only",
  policy: summary.policy,
  quantityScale: 3,
  lines: [lineOne],
  createdByUserId: "engineer@example.invalid",
  createdAt: "2026-08-05T08:00:00Z",
  lifecycle: {
    state: "released",
    version: 4,
    lastEventId: eventReleaseId,
  },
  events: [
    {
      globalId: eventSubmitId,
      eventType: "review_submitted",
      fromState: "draft",
      toState: "in_review",
      fromVersion: 1,
      toVersion: 2,
      actorUserId: "engineer@example.invalid",
      decision: null,
      reason: "Ready for review",
      confirmationIntent: null,
      occurredAt: "2026-08-05T08:10:00Z",
      eventHash: hashA,
    },
    {
      globalId: eventApproveId,
      eventType: "review_approved",
      fromState: "in_review",
      toState: "approved",
      fromVersion: 2,
      toVersion: 3,
      actorUserId: "reviewer@example.invalid",
      decision: "approve",
      reason: "Synthetic review approved",
      confirmationIntent: null,
      occurredAt: "2026-08-05T08:20:00Z",
      eventHash: hashB,
    },
    {
      globalId: eventReleaseId,
      eventType: "released",
      fromState: "approved",
      toState: "released",
      fromVersion: 3,
      toVersion: 4,
      actorUserId: "release@example.invalid",
      decision: null,
      reason: null,
      confirmationIntent: "release_exact_ebom_revision",
      occurredAt: "2026-08-05T08:30:00Z",
      eventHash: hashC,
    },
  ],
  capabilities: {
    revise: false,
    submitReview: false,
    review: false,
    release: false,
    compare: true,
  },
};

const revisionTwo: EngineeringBomRevisionViewModel = {
  ...revisionOne,
  globalId: ebomRevisionTwoId,
  revisionNumber: 2,
  snapshotHash: hashC,
  predecessorRevisionId: ebomRevisionOneId,
  predecessorSnapshotHash: hashB,
  reason: "Increase synthetic housing quantity",
  lines: [lineTwo],
  createdAt: "2026-08-05T09:00:00Z",
  lifecycle: { state: "draft", version: 1, lastEventId: null },
  events: [],
  capabilities: {
    revise: true,
    submitReview: true,
    review: false,
    release: false,
    compare: true,
  },
};

export function engineeringBomListFixture(): EngineeringBomListViewModel {
  return {
    project,
    permissions: { view: true, create: true },
    policies: [policy],
    items: [summary],
  };
}

export function engineeringBomDetailFixture(): EngineeringBomDetailViewModel {
  return {
    project,
    permissions: { view: true, create: true },
    policy,
    ebom: summary,
    revisions: [revisionTwo, revisionOne],
  };
}

export function engineeringBomCommandFixture(): EngineeringBomCommandViewModel {
  return { ebom: summary, revision: revisionTwo };
}

export function releasedEngineeringBomRevisionFixture(): EngineeringBomRevisionViewModel {
  return revisionOne;
}

export function engineeringBomComparisonFixture(): EngineeringBomComparisonViewModel {
  return {
    ebom: summary,
    fromRevision: {
      globalId: revisionOne.globalId,
      revisionNumber: revisionOne.revisionNumber,
      snapshotHash: revisionOne.snapshotHash,
    },
    toRevision: {
      globalId: revisionTwo.globalId,
      revisionNumber: revisionTwo.revisionNumber,
      snapshotHash: revisionTwo.snapshotHash,
    },
    identical: false,
    summary: {
      added: 0,
      removed: 0,
      quantity: 1,
      substitution: 0,
      attribute: 0,
    },
    changes: [
      {
        lineKey: "root",
        changeType: "quantity",
        changedFields: ["quantity"],
        before: lineOne,
        after: lineTwo,
      },
    ],
  };
}
