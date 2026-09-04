import type {
  ReleasedTrialSummaryRevision,
  ReleasedTrialSummarySourceReference,
  ReleasedTrialSummaryWorkspace,
} from "../../src/api/trial-data-source";
import { trialExecutionIds } from "./trial-execution-fixture";
import { trialPlanDetail, trialPlanningIds } from "./trial-planning-fixture";
import { trialQualityIds } from "./trial-quality-fixture";
import { trialReviewIds } from "./trial-review-fixture";

export const releasedTrialSummaryIds = {
  request: "70000000-0000-4000-8000-000000000001",
  revision: "70000000-0000-4000-8000-000000000002",
  summary: "70000000-0000-4000-8000-000000000003",
  successorRequest: "70000000-0000-4000-8000-000000000004",
  successorRevision: "70000000-0000-4000-8000-000000000005",
  successorConclusionRevision: "70000000-0000-4000-8000-000000000006",
} as const;

const hash = (character: string): string => character.repeat(64);

export function releasedTrialSummarySources(): readonly ReleasedTrialSummarySourceReference[] {
  return [
    {
      globalId: trialPlanningIds.revisionOne,
      kind: "trial_plan_revision",
      snapshotHash: hash("1"),
      sourceVersion: 1,
    },
    {
      globalId: trialPlanningIds.round,
      kind: "trial_round",
      snapshotHash: hash("5"),
      sourceVersion: 2,
    },
    {
      globalId: trialExecutionIds.inputLockRevision,
      kind: "trial_input_lock_revision",
      snapshotHash: hash("a"),
      sourceVersion: 1,
    },
    {
      globalId: trialExecutionIds.actualRevision,
      kind: "trial_actual_revision",
      snapshotHash: hash("b"),
      sourceVersion: 1,
    },
    {
      globalId: trialQualityIds.cavityResultRevision,
      kind: "trial_cavity_result_revision",
      snapshotHash: hash("9"),
      sourceVersion: 1,
    },
    {
      globalId: trialQualityIds.trialDefectRevision,
      kind: "trial_defect_revision",
      snapshotHash: hash("7"),
      sourceVersion: 1,
    },
    {
      globalId: trialReviewIds.comparison,
      kind: "trial_round_comparison_snapshot",
      snapshotHash: hash("3"),
      sourceVersion: 1,
    },
    {
      globalId: trialReviewIds.referenceRevision,
      kind: "trial_review_reference_revision",
      snapshotHash: hash("8"),
      sourceVersion: 1,
    },
    {
      globalId: trialReviewIds.conclusionRevision,
      kind: "trial_conclusion_revision",
      snapshotHash: hash("c"),
      sourceVersion: 1,
    },
  ];
}

export function releasedTrialSummaryRevision(
  overrides: Partial<ReleasedTrialSummaryRevision> = {},
): ReleasedTrialSummaryRevision {
  const sources = releasedTrialSummarySources();
  const conclusion = sources.at(-1);
  if (!conclusion)
    throw new Error("The Released Summary fixture requires a conclusion.");
  const firstSource = sources[0];
  if (!firstSource)
    throw new Error("The Released Summary fixture requires a source.");
  const source = (kind: ReleasedTrialSummarySourceReference["kind"]) => {
    const match = sources.find((candidate) => candidate.kind === kind);
    if (!match)
      throw new Error(`The Released Summary fixture requires ${kind}.`);
    return match;
  };
  return {
    conclusionCode: "conditional_pass",
    conclusionRevisionGlobalId: trialReviewIds.conclusionRevision,
    conclusionSnapshotHash: hash("c"),
    conclusionState: "approved",
    conclusionVersion: 1,
    createdAt: "2026-08-15T07:00:00Z",
    createdByUserId: "quality.engineer@example.invalid",
    globalId: releasedTrialSummaryIds.revision,
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    presentationProjection: {
      conclusionCode: "conditional_pass",
      conclusionRevision: conclusion,
      conclusionState: "approved",
      externalEffects: {
        customerApproval: "unavailable",
        externalProjection: "unavailable",
        formalSignature: "unavailable",
        gateDecision: "unavailable",
        productionAcceptance: "unavailable",
      },
      facts: {
        actualParameters: [
          {
            factKey: "injection.pressure",
            sourceReferences: [source("trial_actual_revision")],
            unit: "MPa",
            value: "92",
            valueState: "measured",
          },
        ],
        blockers: [
          {
            factKey: "open_blocking_defects",
            sourceReferences: [source("trial_defect_revision")],
            unit: null,
            value: 1,
            valueState: "open",
          },
        ],
        cavityResults: [
          {
            factKey: "rib.end.width",
            sourceReferences: [source("trial_cavity_result_revision")],
            unit: "mm",
            value: "2.31",
            valueState: "failed",
          },
        ],
        comparison: [
          {
            factKey: "yield",
            sourceReferences: [source("trial_round_comparison_snapshot")],
            unit: "%",
            value: "93.2",
            valueState: "failed",
          },
        ],
        controlledReferences: [
          {
            factKey: "controlled_quality_report",
            sourceReferences: [source("trial_review_reference_revision")],
            unit: null,
            value: true,
            valueState: "informational",
          },
        ],
        defects: [
          {
            factKey: "rib_end_short_shot",
            sourceReferences: [source("trial_defect_revision")],
            unit: null,
            value: "ready_for_verification",
            valueState: "open",
          },
        ],
        inputChanges: [
          {
            factKey: "material.lot_batch",
            sourceReferences: [source("trial_input_lock_revision")],
            unit: null,
            value: "LOT-2026-0810",
            valueState: "informational",
          },
        ],
        samples: [],
      },
      projectGlobalId: trialPlanningIds.project,
      schemaVersion: "npi.released_trial_summary.presentation.v1",
      sourceManifest: sources,
      trialPlanGlobalId: trialPlanningIds.plan,
      trialRoundGlobalId: trialPlanningIds.round,
    },
    presentationProjectionHash: hash("d"),
    projectGlobalId: trialPlanningIds.project,
    reason: "Retain the exact decided Trial conclusion as technical truth.",
    redactionManifest: {
      appliedRuleCodes: [
        "exclude_credentials",
        "exclude_file_content",
        "exclude_private_locators",
        "exclude_provider_payloads",
        "exclude_unapproved_external_projection",
      ],
      excludedSensitiveFieldClasses: [
        "authorization_headers",
        "credentials",
        "file_content",
        "private_paths",
        "private_urls",
        "production_hostnames",
        "provider_payloads",
        "secrets",
        "session_cookies",
      ],
      externalProjection: "unavailable",
      schemaVersion: "npi.released_trial_summary.redaction.v1",
    },
    redactionManifestHash: hash("e"),
    requestId: releasedTrialSummaryIds.request,
    schemaVersion: "npi.released_trial_summary.v1",
    snapshotHash: hash("f"),
    sourceManifest: sources,
    sourceManifestHash: hash("0"),
    summaryGlobalId: releasedTrialSummaryIds.summary,
    summaryVersion: 1,
    tenantId: "npi-one-test",
    traceId: "trace-released-summary-fixture",
    trialPlanGlobalId: trialPlanningIds.plan,
    trialPlanRevisionGlobalId: trialPlanningIds.revisionOne,
    trialPlanRevisionSnapshotHash: firstSource.snapshotHash,
    trialRoundGlobalId: trialPlanningIds.round,
    trialRoundOptimisticVersion: 2,
    trialRoundSnapshotHash: hash("5"),
    versionKeyHash: hash("2"),
    ...overrides,
  };
}

export function releasedTrialSummaryWorkspace(
  overrides: Partial<ReleasedTrialSummaryWorkspace> = {},
): ReleasedTrialSummaryWorkspace {
  const sourceRound = trialPlanDetail().rounds[0];
  if (!sourceRound)
    throw new Error("The Released Summary fixture requires one Round.");
  const trialRound = {
    ...sourceRound,
    currentState: "approved" as const,
    optimisticVersion: 2,
    snapshotHash: hash("5"),
  };
  const revision = releasedTrialSummaryRevision();
  return {
    controlledOutput: {
      mapping: "unavailable",
      sourceGlobalId: revision.globalId,
      sourceObjectType: "released_trial_summary",
      sourceVersion: revision.summaryVersion,
    },
    currentDecidedConclusion: {
      conclusionCode: revision.conclusionCode,
      conclusionVersion: revision.conclusionVersion,
      globalId: revision.conclusionRevisionGlobalId,
      snapshotHash: revision.conclusionSnapshotHash,
      state: revision.conclusionState,
    },
    currentSummaryRevisionGlobalId: revision.globalId,
    holds: {
      customerApproval: "unavailable",
      externalProjection: "unavailable",
      formalRelease: "unavailable",
      gateDecision: "unavailable",
      productionAcceptance: "unavailable",
      signature: "unavailable",
    },
    permissions: {
      requiresExactConclusion: true,
      requiresExactPredecessor: true,
      requiresExactRound: true,
      retain: false,
      revise: false,
      view: true,
    },
    projectGlobalId: trialPlanningIds.project,
    summaryRevisions: [revision],
    trialRound,
    ...overrides,
  };
}

export function emptyReleasedTrialSummaryWorkspace(): ReleasedTrialSummaryWorkspace {
  const workspace = releasedTrialSummaryWorkspace();
  return {
    ...workspace,
    controlledOutput: {
      ...workspace.controlledOutput,
      sourceGlobalId: null,
      sourceVersion: null,
    },
    currentSummaryRevisionGlobalId: null,
    permissions: { ...workspace.permissions, retain: true },
    summaryRevisions: [],
  };
}

export function successorReleasedTrialSummaryWorkspace(): ReleasedTrialSummaryWorkspace {
  const workspace = releasedTrialSummaryWorkspace();
  const predecessor = workspace.summaryRevisions[0];
  if (!predecessor)
    throw new Error("The Released Summary fixture requires a predecessor.");
  const sourceManifest = predecessor.sourceManifest.map((source) =>
    source.kind === "trial_conclusion_revision"
      ? {
          ...source,
          globalId: releasedTrialSummaryIds.successorConclusionRevision,
          snapshotHash: hash("6"),
          sourceVersion: 2,
        }
      : source,
  );
  const conclusionRevision = sourceManifest.at(-1);
  if (conclusionRevision?.kind !== "trial_conclusion_revision")
    throw new Error("The Released Summary fixture requires a conclusion tip.");
  const successor = releasedTrialSummaryRevision({
    conclusionCode: "pass",
    conclusionRevisionGlobalId: conclusionRevision.globalId,
    conclusionSnapshotHash: conclusionRevision.snapshotHash,
    conclusionVersion: conclusionRevision.sourceVersion,
    createdAt: "2026-08-15T08:00:00Z",
    globalId: releasedTrialSummaryIds.successorRevision,
    predecessorGlobalId: predecessor.globalId,
    predecessorSnapshotHash: predecessor.snapshotHash,
    presentationProjection: {
      ...predecessor.presentationProjection,
      conclusionCode: "pass",
      conclusionRevision,
      sourceManifest,
    },
    presentationProjectionHash: hash("7"),
    reason: "Append the later exact decided Trial conclusion.",
    requestId: releasedTrialSummaryIds.successorRequest,
    snapshotHash: hash("8"),
    sourceManifest,
    sourceManifestHash: hash("9"),
    summaryVersion: 2,
    traceId: "trace-released-summary-successor-fixture",
    versionKeyHash: hash("a"),
  });
  return {
    ...workspace,
    controlledOutput: {
      ...workspace.controlledOutput,
      sourceGlobalId: successor.globalId,
      sourceVersion: successor.summaryVersion,
    },
    currentDecidedConclusion: {
      conclusionCode: successor.conclusionCode,
      conclusionVersion: successor.conclusionVersion,
      globalId: successor.conclusionRevisionGlobalId,
      snapshotHash: successor.conclusionSnapshotHash,
      state: successor.conclusionState,
    },
    currentSummaryRevisionGlobalId: successor.globalId,
    summaryRevisions: [predecessor, successor],
  };
}
