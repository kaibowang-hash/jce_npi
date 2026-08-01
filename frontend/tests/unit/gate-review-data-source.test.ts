import { describe, expect, it, vi } from "vitest";

import {
  GateReviewRequestCancelledError,
  isGateReviewResponse,
  isGateReviewResponseForRoute,
  LiveGateReviewDataSource,
  type DecideGateCommand,
  type DecideGateReviewExceptionCommand,
  type GateReviewCommandContext,
  type ReopenGateCommand,
  type RequestGateReviewExceptionCommand,
  type StartGateReviewCommand,
  type SubmitGateReviewCommand,
} from "../../src/api/gate-review-data-source";
import {
  NpiApiError,
  NpiHttpClient,
  NpiTransportError,
} from "../../src/api/http";
import type {
  GateDecisionSummaryViewModel,
  GateReviewAvailablePolicyViewModel,
  GateReviewDependencyChangeViewModel,
  GateReviewExceptionViewModel,
  GateReviewViewModel,
} from "../../src/domain/view-models";
import {
  gateReviewDecisionReadyFixture as reviewRoomDecisionReadyFixture,
  gateReviewExceptionHistoryFixture as reviewRoomExceptionHistoryFixture,
  gateReviewFixture as reviewRoomFixture,
  gateReviewRequiresReviewFixture as reviewRoomRequiresReviewFixture,
} from "../support/gate-review-fixture";
import { gateEvidenceFixture } from "../support/gate-evidence-fixture";
import {
  documentBaselineWorkspaceFixture,
  documentProjectId,
} from "../support/document-fixture";

const projectId = "11111111-1111-1111-1111-111111111111";
const gateId = "22222222-2222-2222-2222-222222222222";
const requirementId = "33333333-3333-3333-3333-333333333333";
const cycleId = "44444444-4444-4444-4444-444444444444";
const successorCycleId = "44444444-4444-4444-4444-555555555555";
const refreshedSuccessorCycleId = "44444444-4444-4444-8444-666666666666";
const policyId = "55555555-5555-5555-5555-555555555555";
const templateId = "66666666-6666-6666-6666-666666666666";
const reviewerId = "77777777-7777-7777-7777-777777777777";
const decisionMemberId = "88888888-8888-8888-8888-888888888888";
const reopenMemberId = "99999999-9999-9999-9999-999999999999";
const exceptionMemberId = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const closureActionId = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
const exceptionId = "cccccccc-cccc-cccc-cccc-cccccccccccc";
const reviewRecordId = "dddddddd-dddd-dddd-dddd-dddddddddddd";
const decisionId = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee";
const inputHash = "1".repeat(64);
const policyHash = "2".repeat(64);
const templateHash = "3".repeat(64);
const requirementHash = "4".repeat(64);
const reviewHash = "5".repeat(64);
const decisionHash = "6".repeat(64);
const csrfToken = "c".repeat(32);
const idempotencyKey = "command-retry-key-0001";

function recordAt(
  values: readonly Record<string, unknown>[],
  index: number,
): Record<string, unknown> {
  const value = values[index];
  if (!value) throw new Error(`Missing fixture record ${String(index)}.`);
  return value;
}

function policyDefinition(): GateReviewAvailablePolicyViewModel {
  return {
    policyRef: {
      globalId: policyId,
      version: 1,
      snapshotHash: policyHash,
    },
    authoritySlots: [
      { slot: "technical_review", purpose: "review" },
      { slot: "decision_authority", purpose: "decision" },
      { slot: "reopen_authority", purpose: "reopen" },
      { slot: "exception_authority", purpose: "exception" },
    ],
    exceptionRules: [
      {
        kind: "controlled_deviation",
        eligibleRequirementKeys: ["DESIGN_BASELINE"],
        approvalAuthoritySlot: "exception_authority",
        maximumValidityDays: 30,
        requiredClosureActionKind: "action",
      },
    ],
  };
}

function activeFixture(): GateReviewViewModel {
  return {
    project: {
      globalId: projectId,
      businessCode: "SYN-PROJECT-001",
      title: "Synthetic project",
    },
    gate: {
      globalId: gateId,
      key: "G1",
      title: "Synthetic Gate",
      reviewState: "in_review",
      version: 1,
      currentCycleGlobalId: cycleId,
      latestDecisionGlobalId: null,
      latestDecisionHash: null,
      latestDecisionOutcome: null,
      downstreamDecisionCurrent: false,
    },
    evidence: {
      project: {
        globalId: projectId,
        businessCode: "SYN-PROJECT-001",
        title: "Synthetic project",
      },
      gate: {
        globalId: gateId,
        key: "G1",
        title: "Synthetic Gate",
        state: "not_started",
        version: 1,
        dueDate: "2026-08-15",
        templateRef: {
          globalId: templateId,
          version: 1,
          snapshotHash: templateHash,
        },
        requirementSnapshotHash: requirementHash,
        frozenAt: "2026-07-24T10:00:00Z",
        frozenBy: "Administrator",
      },
      requirements: [
        {
          globalId: requirementId,
          key: "DESIGN_BASELINE",
          title: "Synthetic design baseline",
          classification: "required",
          priority: "P1",
          owner: {
            memberId: reviewerId,
            userId: "reviewer@example.invalid",
            displayName: "Synthetic Reviewer",
          },
          reviewers: [
            {
              memberId: decisionMemberId,
              userId: "decision@example.invalid",
              displayName: "Synthetic Decision Authority",
            },
          ],
          dueDate: "2026-08-10",
          allowedEvidenceKinds: ["wbs_item"],
          evidenceState: "missing",
          evidence: [],
        },
      ],
      baselineImpacts: [],
      summary: {
        requiredCount: 1,
        missingRequiredCount: 1,
        unsafeScanCount: 0,
        evidenceCount: 0,
      },
      permissions: {
        canView: true,
        canAttachEvidence: false,
        canAdminister: false,
      },
    },
    exceptionRequestOptions: [
      {
        requirementGlobalId: requirementId,
        requirementKey: "DESIGN_BASELINE",
        kind: "controlled_deviation",
        maximumValidityDays: 30,
        closureActionGlobalIds: [closureActionId],
      },
    ],
    decisionReadiness: {
      allowedOutcomes: [],
      blockedReasons: [
        { outcome: "pass", code: "DECISION_AUTHORITY_REQUIRED" },
        {
          outcome: "conditional_pass",
          code: "DECISION_AUTHORITY_REQUIRED",
        },
        { outcome: "reject", code: "DECISION_AUTHORITY_REQUIRED" },
      ],
    },
    activeCycle: {
      globalId: cycleId,
      number: 1,
      trigger: "manual_start",
      state: "active",
      version: 1,
      policyRef: {
        globalId: policyId,
        version: 1,
        snapshotHash: policyHash,
      },
      policyDefinition: policyDefinition(),
      inputHash,
      bindings: [
        {
          slot: "technical_review",
          memberGlobalId: reviewerId,
          userId: "reviewer@example.invalid",
          displayName: "Synthetic Reviewer",
        },
        {
          slot: "decision_authority",
          memberGlobalId: decisionMemberId,
          userId: "decision@example.invalid",
          displayName: "Synthetic Decision Authority",
        },
        {
          slot: "reopen_authority",
          memberGlobalId: reopenMemberId,
          userId: "reopen@example.invalid",
          displayName: "Synthetic Reopen Authority",
        },
        {
          slot: "exception_authority",
          memberGlobalId: exceptionMemberId,
          userId: "exception@example.invalid",
          displayName: "Synthetic Exception Authority",
        },
      ],
      selectedSteps: [
        {
          stepKey: "TECHNICAL_REVIEW",
          sequence: 1,
          slot: "technical_review",
          assignedMember: {
            memberGlobalId: reviewerId,
            userId: "reviewer@example.invalid",
            displayName: "Synthetic Reviewer",
          },
          state: "available",
          review: null,
        },
      ],
      exceptions: [],
      startedAt: "2026-07-24T10:01:00Z",
      startedBy: "Administrator",
    },
    decisions: [],
    availablePolicies: [policyDefinition()],
    eligibleMembers: [
      {
        memberGlobalId: reviewerId,
        userId: "reviewer@example.invalid",
        displayName: "Synthetic Reviewer",
      },
      {
        memberGlobalId: decisionMemberId,
        userId: "decision@example.invalid",
        displayName: "Synthetic Decision Authority",
      },
      {
        memberGlobalId: reopenMemberId,
        userId: "reopen@example.invalid",
        displayName: "Synthetic Reopen Authority",
      },
      {
        memberGlobalId: exceptionMemberId,
        userId: "exception@example.invalid",
        displayName: "Synthetic Exception Authority",
      },
    ],
    eligibleClosureActions: [
      {
        globalId: closureActionId,
        title: "Close the synthetic deviation",
        state: "open",
        stateLabelSource: "Open",
        version: 1,
      },
    ],
    blockers: [],
    dependencyChanges: [],
    permissions: {
      canView: true,
      canStartReview: false,
      canReview: true,
      canRequestException: true,
      canApproveException: false,
      canDecide: false,
      canReopen: false,
    },
  };
}

function withGateVersion(
  fixture: GateReviewViewModel,
  version: number,
): GateReviewViewModel {
  return {
    ...fixture,
    gate: { ...fixture.gate, version },
    evidence: {
      ...fixture.evidence,
      gate: { ...fixture.evidence.gate, version },
    },
  };
}

function submittedFixture(): GateReviewViewModel {
  const fixture = activeFixture();
  const cycle = fixture.activeCycle;
  if (!cycle) throw new Error("The fixture requires an active cycle.");
  const selectedStep = cycle.selectedSteps[0];
  if (!selectedStep) throw new Error("The fixture requires a review step.");
  return {
    ...fixture,
    activeCycle: {
      ...cycle,
      version: 2,
      selectedSteps: [
        {
          ...selectedStep,
          state: "approved",
          review: {
            globalId: reviewRecordId,
            stepKey: "TECHNICAL_REVIEW",
            outcome: "approved",
            opinion: "Approved synthetic input.",
            actor: "reviewer@example.invalid",
            reviewedAt: "2026-07-24T10:02:00Z",
            inputHash,
            snapshotHash: reviewHash,
          },
        },
      ],
    },
    permissions: {
      ...fixture.permissions,
      canReview: false,
      canDecide: false,
    },
  };
}

function pendingException(): GateReviewExceptionViewModel {
  return {
    allowedOutcomes: [],
    globalId: exceptionId,
    requirementGlobalId: requirementId,
    requirementKey: "DESIGN_BASELINE",
    kind: "controlled_deviation",
    reason: "Synthetic controlled reason.",
    risk: "Synthetic controlled risk.",
    requester: {
      memberGlobalId: reviewerId,
      userId: "reviewer@example.invalid",
      displayName: "Synthetic Reviewer",
    },
    requestedAt: "2026-07-24T10:03:00Z",
    expiresAt: "2026-08-01T10:03:00Z",
    requestSchemaVersion: 2,
    closureActionRef: {
      globalId: closureActionId,
      snapshotHash: "9".repeat(64),
      version: 1,
    },
    state: "pending",
    version: 1,
    requestSnapshotHash: "7".repeat(64),
    decision: null,
  };
}

function exceptionFixture(decided = false): GateReviewViewModel {
  const fixture = activeFixture();
  const cycle = fixture.activeCycle;
  if (!cycle) throw new Error("The fixture requires an active cycle.");
  const exception = pendingException();
  return {
    ...fixture,
    activeCycle: {
      ...cycle,
      version: decided ? 3 : 2,
      exceptions: [
        decided
          ? {
              ...exception,
              allowedOutcomes: [],
              state: "approved",
              version: 2,
              decision: {
                outcome: "approved",
                approver: {
                  memberGlobalId: exceptionMemberId,
                  userId: "exception@example.invalid",
                  displayName: "Synthetic Exception Authority",
                },
                opinion: "Approved synthetic exception.",
                decidedAt: "2026-07-24T10:04:00Z",
                snapshotHash: "8".repeat(64),
              },
            }
          : {
              ...exception,
              allowedOutcomes: ["approved", "rejected"],
            },
      ],
    },
    permissions: {
      ...fixture.permissions,
      canRequestException: true,
      canApproveException: !decided,
    },
  };
}

function requestedExceptionFixture(): GateReviewViewModel {
  const fixture = exceptionFixture();
  const cycle = fixture.activeCycle;
  if (!cycle) throw new Error("The fixture requires an active cycle.");
  return {
    ...fixture,
    activeCycle: {
      ...cycle,
      exceptions: cycle.exceptions.map((exception) => ({
        ...exception,
        allowedOutcomes: [],
      })),
    },
    permissions: {
      ...fixture.permissions,
      canApproveException: false,
    },
  };
}

function decisionSummary(current: boolean): GateDecisionSummaryViewModel {
  return {
    globalId: decisionId,
    cycleGlobalId: cycleId,
    outcome: "pass",
    inputHash,
    snapshotHash: decisionHash,
    decidedAt: "2026-07-24T10:05:00Z",
    decidedBy: "decision@example.invalid",
    current,
    detail: {
      lineageHash: "f".repeat(64),
      cycleNumber: 1,
      policyRef: {
        globalId: policyId,
        version: 1,
        snapshotHash: policyHash,
      },
      inputSnapshot: {
        schemaVersion: 1,
        gateGlobalId: gateId,
        projectGlobalId: projectId,
        tenantId: "synthetic-tenant",
        gateVersion: 1,
        requirements: [
          {
            globalId: requirementId,
            requirementKey: "DESIGN_BASELINE",
            priority: "P1",
            sourceVersion: 1,
            sourceHash: requirementHash,
            evidenceComplete: false,
          },
        ],
        evidence: [],
        blockers: [],
        dependencies: [
          {
            kind: "gate_input_snapshot",
            globalId: gateId,
            version: 1,
            snapshotHash: requirementHash,
          },
        ],
      },
      reviewHashes: [reviewHash],
      exceptionHashes: [],
      cycleVersion: 2,
    },
  };
}

function decidedFixture(): GateReviewViewModel {
  const fixture = withGateVersion(submittedFixture(), 2);
  const cycle = fixture.activeCycle;
  if (!cycle) throw new Error("The fixture requires an active cycle.");
  return {
    ...fixture,
    gate: {
      ...fixture.gate,
      reviewState: "decided",
      latestDecisionGlobalId: decisionId,
      latestDecisionHash: decisionHash,
      latestDecisionOutcome: "pass",
      downstreamDecisionCurrent: true,
    },
    activeCycle: { ...cycle, state: "decided", version: 3 },
    decisionReadiness: {
      allowedOutcomes: [],
      blockedReasons: [
        { outcome: "pass", code: "REVIEW_CYCLE_CLOSED" },
        { outcome: "conditional_pass", code: "REVIEW_CYCLE_CLOSED" },
        { outcome: "reject", code: "REVIEW_CYCLE_CLOSED" },
      ],
    },
    exceptionRequestOptions: [],
    decisions: [decisionSummary(true)],
    permissions: {
      canView: true,
      canStartReview: false,
      canReview: false,
      canRequestException: false,
      canApproveException: false,
      canDecide: false,
      canReopen: true,
    },
  };
}

function reopenedFixture(): GateReviewViewModel {
  const fixture = withGateVersion(decidedFixture(), 3);
  const cycle = fixture.activeCycle;
  if (!cycle) throw new Error("The fixture requires an active cycle.");
  return {
    ...fixture,
    gate: {
      ...fixture.gate,
      currentCycleGlobalId: successorCycleId,
      downstreamDecisionCurrent: false,
      reviewState: "in_review",
    },
    activeCycle: {
      ...cycle,
      globalId: successorCycleId,
      number: 2,
      exceptions: [],
      selectedSteps: cycle.selectedSteps.map((step) => ({
        ...step,
        review: null,
        state: "available",
      })),
      state: "active",
      trigger: "manual_reopen",
      version: 1,
    },
    decisions: [decisionSummary(false)],
    decisionReadiness: {
      allowedOutcomes: [],
      blockedReasons: [
        { outcome: "pass", code: "DECISION_AUTHORITY_REQUIRED" },
        {
          outcome: "conditional_pass",
          code: "DECISION_AUTHORITY_REQUIRED",
        },
        { outcome: "reject", code: "DECISION_AUTHORITY_REQUIRED" },
      ],
    },
    permissions: {
      canApproveException: false,
      canDecide: false,
      canRequestException: false,
      canReopen: false,
      canReview: false,
      canStartReview: false,
      canView: true,
    },
  };
}

function dependencyChange(
  overrides: Partial<GateReviewDependencyChangeViewModel> = {},
): GateReviewDependencyChangeViewModel {
  return {
    eventGlobalId: "12121212-1212-1212-1212-121212121212",
    eventType: "invalidated",
    priorCycleGlobalId: cycleId,
    successorCycleGlobalId: successorCycleId,
    impactActionGlobalId: null,
    oldInputHash: inputHash,
    newInputHash: "b".repeat(64),
    priorDecisionGlobalId: decisionId,
    priorDecisionLineageHash: "f".repeat(64),
    actorUserId: "npi-gate-review-dependency-system",
    initiatedByUserId: "reviewer@example.invalid",
    occurredAt: "2026-07-24T10:10:00Z",
    reason: "The exact synthetic Gate input changed.",
    ...overrides,
  };
}

function dependencyFixture(): GateReviewViewModel {
  const fixture = decidedFixture();
  const cycle = fixture.activeCycle;
  if (!cycle) throw new Error("The fixture requires an active cycle.");
  return {
    ...fixture,
    activeCycle: {
      ...cycle,
      globalId: successorCycleId,
      inputHash: "b".repeat(64),
      number: 2,
      selectedSteps: cycle.selectedSteps.map((step) => ({
        ...step,
        review: null,
        state: "waiting",
      })),
      state: "active",
      trigger: "dependency_change",
      version: 1,
    },
    decisions: fixture.decisions.map((decision) => ({
      ...decision,
      current: false,
    })),
    dependencyChanges: [
      dependencyChange(),
      dependencyChange({
        eventGlobalId: "14141414-1414-1414-1414-141414141414",
        eventType: "refreshed",
        priorCycleGlobalId: "15151515-1515-1515-1515-151515151515",
        successorCycleGlobalId: "16161616-1616-1616-1616-161616161616",
        oldInputHash: "c".repeat(64),
        newInputHash: "d".repeat(64),
        priorDecisionGlobalId: null,
        priorDecisionLineageHash: null,
        initiatedByUserId: null,
        occurredAt: "2026-07-24T10:09:00.123456Z",
      }),
    ],
    gate: {
      ...fixture.gate,
      currentCycleGlobalId: successorCycleId,
      downstreamDecisionCurrent: false,
      reviewState: "requires_review",
    },
    permissions: {
      canApproveException: false,
      canDecide: false,
      canRequestException: false,
      canReopen: false,
      canReview: false,
      canStartReview: true,
      canView: true,
    },
  };
}

function refreshedWithoutDecisionFixture(): GateReviewViewModel {
  const fixture = withGateVersion(activeFixture(), 2);
  const cycle = fixture.activeCycle;
  if (!cycle) throw new Error("The fixture requires an active cycle.");
  const refreshedInputHash = "b".repeat(64);
  return {
    ...fixture,
    activeCycle: {
      ...cycle,
      exceptions: [],
      globalId: successorCycleId,
      inputHash: refreshedInputHash,
      number: 2,
      selectedSteps: cycle.selectedSteps.map((step) => ({
        ...step,
        review: null,
        state: "waiting",
      })),
      state: "active",
      trigger: "dependency_change",
      version: 1,
    },
    dependencyChanges: [
      dependencyChange({
        eventType: "refreshed",
        newInputHash: refreshedInputHash,
        priorDecisionGlobalId: null,
        priorDecisionLineageHash: null,
      }),
    ],
    exceptionRequestOptions: [],
    gate: {
      ...fixture.gate,
      currentCycleGlobalId: successorCycleId,
      reviewState: "requires_review",
    },
    permissions: {
      canApproveException: false,
      canDecide: false,
      canRequestException: false,
      canReopen: false,
      canReview: false,
      canStartReview: true,
      canView: true,
    },
  };
}

function refreshedWithInheritedDecisionFixture(): GateReviewViewModel {
  const fixture = withGateVersion(dependencyFixture(), 3);
  const cycle = fixture.activeCycle;
  if (!cycle) throw new Error("The fixture requires an active cycle.");
  const refreshedInputHash = "c".repeat(64);
  return {
    ...fixture,
    activeCycle: {
      ...cycle,
      globalId: refreshedSuccessorCycleId,
      inputHash: refreshedInputHash,
      number: 3,
    },
    dependencyChanges: [
      dependencyChange({
        eventGlobalId: "17171717-1717-4717-8717-171717171717",
        eventType: "refreshed",
        newInputHash: refreshedInputHash,
        occurredAt: "2026-07-24T10:11:00Z",
        oldInputHash: "b".repeat(64),
        priorCycleGlobalId: successorCycleId,
        successorCycleGlobalId: refreshedSuccessorCycleId,
      }),
      ...fixture.dependencyChanges,
    ],
    gate: {
      ...fixture.gate,
      currentCycleGlobalId: refreshedSuccessorCycleId,
    },
  };
}

function context(
  signal = new AbortController().signal,
): GateReviewCommandContext {
  return { csrfToken, idempotencyKey, signal };
}

describe("Gate review response validation", () => {
  it("accepts the exact closed review workspace and route identities", () => {
    const fixture = activeFixture();
    expect(isGateReviewResponse(fixture)).toBe(true);
    expect(isGateReviewResponseForRoute(fixture, projectId, gateId)).toBe(true);
    expect(
      isGateReviewResponseForRoute(
        fixture,
        "ffffffff-ffff-ffff-ffff-ffffffffffff",
        gateId,
      ),
    ).toBe(false);
  });

  it("accepts preserved historical decisions after reopen without calling them current", () => {
    expect(isGateReviewResponse(reopenedFixture())).toBe(true);
  });

  it("accepts an exact non-file release baseline in frozen decision input", () => {
    const fixture = decidedFixture();
    const decision = fixture.decisions[0];
    if (!decision) throw new Error("The fixture requires a decision.");
    decision.detail.inputSnapshot.evidence = [
      {
        globalId: "34343434-3434-4343-8343-343434343434",
        requirementGlobalId: requirementId,
        evidenceKind: "release_baseline",
        sourceGlobalId: "35353535-3535-4535-8535-353535353535",
        sourceVersion: 1,
        sourceHash: "a".repeat(64),
        isFile: false,
        fileSafe: true,
      },
    ];
    expect(isGateReviewResponse(fixture)).toBe(true);

    const baselineEvidence = decision.detail.inputSnapshot.evidence[0];
    if (!baselineEvidence) throw new Error("The fixture requires evidence.");
    baselineEvidence.fileSafe = false;
    expect(isGateReviewResponse(fixture)).toBe(false);
  });

  it("accepts a decided Gate whose latest historical decision is no longer downstream-current", () => {
    const fixture = structuredClone(decidedFixture());
    fixture.gate.downstreamDecisionCurrent = false;
    const decision = fixture.decisions[0];
    if (!decision) throw new Error("The fixture requires a decision.");
    decision.current = false;
    expect(isGateReviewResponse(fixture)).toBe(true);
  });

  it("accepts closed v1 legacy, v1 exact-collision, and v2 exact exception profiles", () => {
    const legacy = structuredClone(requestedExceptionFixture());
    const legacyException = legacy.activeCycle?.exceptions[0];
    if (!legacyException) throw new Error("The fixture requires an exception.");
    legacyException.requestSchemaVersion = 1;
    legacyException.closureActionRef = {
      globalId: closureActionId,
      version: null,
      snapshotHash: null,
    };
    expect(isGateReviewResponse(legacy)).toBe(true);

    const collision = structuredClone(exceptionFixture());
    const collisionException = collision.activeCycle?.exceptions[0];
    if (!collisionException)
      throw new Error("The fixture requires an exception.");
    collisionException.requestSchemaVersion = 1;
    expect(isGateReviewResponse(collision)).toBe(true);

    expect(isGateReviewResponse(exceptionFixture())).toBe(true);
  });

  it("rejects a v2 exception with a legacy closure-action reference", () => {
    const fixture = structuredClone(requestedExceptionFixture());
    const exception = fixture.activeCycle?.exceptions[0];
    if (!exception) throw new Error("The fixture requires an exception.");
    exception.closureActionRef = {
      globalId: closureActionId,
      version: null,
      snapshotHash: null,
    };
    expect(isGateReviewResponse(fixture)).toBe(false);
  });

  it("accepts reconstructable review, exception, and decision audit projections", () => {
    expect(isGateReviewResponse(reviewRoomFixture())).toBe(true);
    expect(isGateReviewResponse(reviewRoomExceptionHistoryFixture())).toBe(
      true,
    );
    expect(isGateReviewResponse(reviewRoomDecisionReadyFixture())).toBe(true);
  });

  it("accepts a frozen policy definition and newest-first dependency lineage while rejecting an impossible active superseded cycle", () => {
    expect(isGateReviewResponse(dependencyFixture())).toBe(true);
    const superseded = activeFixture();
    expect(
      isGateReviewResponse({
        ...superseded,
        activeCycle: superseded.activeCycle
          ? { ...superseded.activeCycle, state: "superseded" }
          : null,
        permissions: {
          canView: true,
          canStartReview: false,
          canReview: false,
          canRequestException: false,
          canApproveException: false,
          canDecide: false,
          canReopen: false,
        },
      }),
    ).toBe(false);
  });

  it("accepts active dependency refreshes with no decision history or an inherited latest decision", () => {
    expect(isGateReviewResponse(refreshedWithoutDecisionFixture())).toBe(true);
    expect(isGateReviewResponse(refreshedWithInheritedDecisionFixture())).toBe(
      true,
    );
  });

  it.each([
    [
      "an unknown response property",
      (fixture: Record<string, unknown>) => {
        fixture.rawSnapshot = { untrusted: true };
      },
    ],
    [
      "a missing frozen requirement identity",
      (fixture: Record<string, unknown>) => {
        const evidence = fixture.evidence as Record<string, unknown>;
        const requirements = evidence.requirements as Record<string, unknown>[];
        delete requirements[0]?.globalId;
      },
    ],
    [
      "an invalid nested timestamp",
      (fixture: Record<string, unknown>) => {
        const activeCycle = fixture.activeCycle as Record<string, unknown>;
        activeCycle.startedAt = "2026-02-30T10:00:00Z";
      },
    ],
    [
      "a step assignment that differs from its frozen binding",
      (fixture: Record<string, unknown>) => {
        const activeCycle = fixture.activeCycle as Record<string, unknown>;
        const steps = activeCycle.selectedSteps as Record<string, unknown>[];
        const member = steps[0]?.assignedMember as Record<string, unknown>;
        member.memberGlobalId = decisionMemberId;
      },
    ],
    [
      "a response Gate version that differs from embedded evidence",
      (fixture: Record<string, unknown>) => {
        const gate = fixture.gate as Record<string, unknown>;
        gate.version = 9;
      },
    ],
    [
      "a frozen policy definition that differs from its cycle reference",
      (fixture: Record<string, unknown>) => {
        const activeCycle = fixture.activeCycle as Record<string, unknown>;
        const definition = activeCycle.policyDefinition as Record<
          string,
          unknown
        >;
        const policyRef = definition.policyRef as Record<string, unknown>;
        policyRef.snapshotHash = "0".repeat(64);
      },
    ],
    [
      "an unpublished closure-action state label source",
      (fixture: Record<string, unknown>) => {
        const actions = fixture.eligibleClosureActions as Record<
          string,
          unknown
        >[];
        const action = actions[0];
        if (!action) throw new Error("The fixture requires a closure action.");
        action.stateLabelSource = "Unpublished state";
      },
    ],
    [
      "an unpublished blocker state label source",
      (fixture: Record<string, unknown>) => {
        fixture.blockers = [
          {
            globalId: "18181818-1818-1818-1818-181818181818",
            kind: "issue",
            title: "Synthetic blocker",
            state: "open",
            stateLabelSource: "Unpublished state",
            dueAt: "2026-07-25T10:00:00Z",
            owner: "owner@example.invalid",
          },
        ];
      },
    ],
    [
      "a fake current decision after invalidation",
      (fixture: Record<string, unknown>) => {
        const gate = fixture.gate as Record<string, unknown>;
        gate.downstreamDecisionCurrent = false;
        const decisions = fixture.decisions as Record<string, unknown>[];
        const decision = decisions[0];
        if (!decision) throw new Error("The fixture requires a decision.");
        decision.current = true;
      },
      decidedFixture,
    ],
    [
      "a decision without its immutable detail",
      (fixture: Record<string, unknown>) => {
        const decisions = fixture.decisions as Record<string, unknown>[];
        delete recordAt(decisions, 0).detail;
      },
      decidedFixture,
    ],
    [
      "a legacy closure-action identity in an exception response",
      (fixture: Record<string, unknown>) => {
        const cycle = fixture.activeCycle as Record<string, unknown>;
        const exceptions = cycle.exceptions as Record<string, unknown>[];
        const exception = recordAt(exceptions, 0);
        delete exception.closureActionRef;
        exception.closureActionGlobalId = closureActionId;
      },
      exceptionFixture,
    ],
  ])(
    "rejects %s",
    (
      _label,
      mutate: (fixture: Record<string, unknown>) => void,
      factory: () => GateReviewViewModel = activeFixture,
    ) => {
      const fixture = structuredClone(factory()) as unknown as Record<
        string,
        unknown
      >;
      mutate(fixture);
      expect(isGateReviewResponse(fixture)).toBe(false);
    },
  );

  it.each([
    [
      "an unknown dependency property",
      (changes: Record<string, unknown>[]) => {
        recordAt(changes, 0).rawDelta = { unsafe: true };
      },
    ],
    [
      "unpaired prior-decision lineage",
      (changes: Record<string, unknown>[]) => {
        recordAt(changes, 0).priorDecisionLineageHash = null;
      },
    ],
    [
      "decision lineage that differs from the immutable decision detail",
      (changes: Record<string, unknown>[]) => {
        recordAt(changes, 0).priorDecisionLineageHash = "e".repeat(64);
      },
    ],
    [
      "equal old and new input hashes",
      (changes: Record<string, unknown>[]) => {
        recordAt(changes, 0).newInputHash = recordAt(changes, 0).oldInputHash;
      },
    ],
    [
      "equal prior and successor cycles",
      (changes: Record<string, unknown>[]) => {
        recordAt(changes, 0).successorCycleGlobalId = recordAt(
          changes,
          0,
        ).priorCycleGlobalId;
      },
    ],
    [
      "duplicate dependency event identities",
      (changes: Record<string, unknown>[]) => {
        recordAt(changes, 1).eventGlobalId = recordAt(changes, 0).eventGlobalId;
      },
    ],
    [
      "oldest-first dependency ordering",
      (changes: Record<string, unknown>[]) => {
        recordAt(changes, 1).occurredAt = "2026-07-24T10:11:00Z";
      },
    ],
    [
      "an unresolved prior decision identity",
      (changes: Record<string, unknown>[]) => {
        recordAt(changes, 0).priorDecisionGlobalId =
          "19191919-1919-1919-1919-191919191919";
      },
    ],
  ])("rejects %s", (_label, mutate) => {
    const fixture = structuredClone(dependencyFixture()) as unknown as Record<
      string,
      unknown
    >;
    const changes = fixture.dependencyChanges as Record<string, unknown>[];
    mutate(changes);
    expect(isGateReviewResponse(fixture)).toBe(false);
  });

  it("accepts an omitted legacy impact-action identity while fixtures emit an explicit null", () => {
    const fixture = structuredClone(dependencyFixture()) as unknown as Record<
      string,
      unknown
    >;
    const changes = fixture.dependencyChanges as Record<string, unknown>[];
    expect(recordAt(changes, 0).impactActionGlobalId).toBeNull();
    delete recordAt(changes, 0).impactActionGlobalId;
    expect(isGateReviewResponse(fixture)).toBe(true);
  });

  it.each([
    [
      "a review actor other than the frozen assigned member",
      (fixture: GateReviewViewModel) => {
        const cycle = fixture.activeCycle;
        const review = cycle?.selectedSteps.find(
          (step) => step.review !== null,
        )?.review;
        if (!review) throw new Error("The fixture requires a review.");
        review.actor = "different.reviewer@example.invalid";
      },
      reviewRoomFixture,
    ],
    [
      "a later review sequence exposed before every prior step approves",
      (fixture: GateReviewViewModel) => {
        const step = fixture.activeCycle?.selectedSteps.find(
          (candidate) => candidate.sequence === 2,
        );
        if (!step) throw new Error("The fixture requires a later step.");
        step.state = "available";
      },
      reviewRoomFixture,
    ],
    [
      "duplicate immutable review record identities",
      (fixture: GateReviewViewModel) => {
        const reviews =
          fixture.activeCycle?.selectedSteps.flatMap((step) =>
            step.review ? [step.review] : [],
          ) ?? [];
        if (!reviews[0] || !reviews[1])
          throw new Error("The fixture requires two reviews.");
        reviews[1].globalId = reviews[0].globalId;
      },
      reviewRoomDecisionReadyFixture,
    ],
    [
      "duplicate immutable review snapshot hashes",
      (fixture: GateReviewViewModel) => {
        const reviews =
          fixture.activeCycle?.selectedSteps.flatMap((step) =>
            step.review ? [step.review] : [],
          ) ?? [];
        if (!reviews[0] || !reviews[1])
          throw new Error("The fixture requires two reviews.");
        reviews[1].snapshotHash = reviews[0].snapshotHash;
      },
      reviewRoomDecisionReadyFixture,
    ],
    [
      "a P0 requirement exception",
      (fixture: GateReviewViewModel) => {
        const exception = fixture.activeCycle?.exceptions[0];
        const requirement = fixture.evidence.requirements.find(
          (candidate) => candidate.globalId === exception?.requirementGlobalId,
        );
        if (!requirement)
          throw new Error("The fixture requires an excepted requirement.");
        requirement.priority = "P0";
      },
      reviewRoomExceptionHistoryFixture,
    ],
    [
      "an exception requester equal to the frozen approver",
      (fixture: GateReviewViewModel) => {
        const cycle = fixture.activeCycle;
        const exception = cycle?.exceptions[0];
        const approver = exception?.decision?.approver;
        if (!exception || !approver)
          throw new Error("The fixture requires an exception decision.");
        exception.requester = approver;
      },
      reviewRoomExceptionHistoryFixture,
    ],
    [
      "an exception decision by someone other than the frozen authority",
      (fixture: GateReviewViewModel) => {
        const decision = fixture.activeCycle?.exceptions[0]?.decision;
        if (!decision)
          throw new Error("The fixture requires an exception decision.");
        decision.approver = {
          displayName: "Different approver",
          memberGlobalId: reviewerId,
          userId: "different.approver@example.invalid",
        };
      },
      reviewRoomExceptionHistoryFixture,
    ],
    [
      "a current Gate decision by someone other than the frozen authority",
      (fixture: GateReviewViewModel) => {
        const decision = fixture.decisions[0];
        if (!decision) throw new Error("The fixture requires a decision.");
        decision.decidedBy = "different.authority@example.invalid";
      },
      decidedFixture,
    ],
    [
      "a dependency reason beyond the contracted 140 characters",
      (fixture: GateReviewViewModel) => {
        const change = fixture.dependencyChanges[0];
        if (!change)
          throw new Error("The fixture requires a dependency event.");
        change.reason = "x".repeat(141);
      },
      reviewRoomRequiresReviewFixture,
    ],
    [
      "a refreshed requires-review successor that drops its retained decision lineage",
      (fixture: GateReviewViewModel) => {
        const change = fixture.dependencyChanges[0];
        if (!change)
          throw new Error("The fixture requires a dependency event.");
        change.priorDecisionGlobalId = null;
        change.priorDecisionLineageHash = null;
      },
      refreshedWithInheritedDecisionFixture,
    ],
    [
      "an invalidated event whose prior cycle is later than its decision",
      (fixture: GateReviewViewModel) => {
        const change = fixture.dependencyChanges[0];
        if (!change)
          throw new Error("The fixture requires a dependency event.");
        change.eventType = "invalidated";
      },
      refreshedWithInheritedDecisionFixture,
    ],
    [
      "a latest-decision pointer that is not the ordered last decision",
      (fixture: GateReviewViewModel) => {
        const firstDecision = fixture.decisions[0];
        if (!firstDecision)
          throw new Error("The fixture requires an existing decision.");
        fixture.decisions = [
          ...fixture.decisions,
          {
            ...firstDecision,
            cycleGlobalId: "20202020-2020-4020-8020-202020202020",
            current: false,
            detail: {
              ...firstDecision.detail,
              cycleNumber: 2,
            },
            globalId: "21212121-2121-4121-8121-212121212121",
          },
        ];
      },
      decidedFixture,
    ],
  ])("rejects %s", (_label, mutate, factory) => {
    const fixture = structuredClone(factory());
    mutate(fixture);
    expect(isGateReviewResponse(fixture)).toBe(false);
  });
});

describe("live Gate review transport", () => {
  it("loads exact Project release baselines for the Gate source selector", async () => {
    const fixture = documentBaselineWorkspaceFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(fixture as T));
    const signal = new AbortController().signal;

    await expect(
      new LiveGateReviewDataSource(http).loadDocumentBaselines(
        documentProjectId,
        signal,
      ),
    ).resolves.toEqual(fixture);
    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(`/projects/${documentProjectId}/document-baselines`);
    expect(init).toEqual({ signal });
    expect(options).toMatchObject({
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
    expect(options?.validate?.(fixture)).toBe(true);
  });

  it("attaches one exact baseline source and reloads authoritative Gate review truth", async () => {
    const review = reviewRoomFixture();
    const baseline = documentBaselineWorkspaceFixture().items[0];
    if (!baseline)
      throw new Error("The fixture requires one release baseline.");
    const requirement = review.evidence.requirements[0];
    if (!requirement) throw new Error("The fixture requires one requirement.");
    const reference = {
      globalId: "31313131-3131-4313-8313-313131313131",
      kind: "release_baseline" as const,
      sourceObjectType: "release_baseline" as const,
      sourceGlobalId: baseline.globalId,
      revision: baseline.version,
      objectHash: baseline.snapshotHash,
      createdAt: "2026-07-31T12:00:00Z",
      createdBy: "engineering.lead@example.invalid",
      baseline,
    };
    const evidence = gateEvidenceFixture({
      requirements: review.evidence.requirements.map((candidate, index) =>
        index === 0
          ? {
              ...candidate,
              allowedEvidenceKinds: [
                ...candidate.allowedEvidenceKinds,
                "release_baseline" as const,
              ],
              evidence: [...candidate.evidence, reference],
            }
          : candidate,
      ),
      summary: {
        ...review.evidence.summary,
        evidenceCount: review.evidence.summary.evidenceCount + 1,
      },
    });
    const refreshed = { ...review, evidence };
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementationOnce(
        <T>(): Promise<T> => Promise.resolve(evidence as T),
      )
      .mockImplementationOnce(
        <T>(): Promise<T> => Promise.resolve(refreshed as T),
      );
    const source = new LiveGateReviewDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.attachEvidence(
        review.project.globalId,
        review.gate.globalId,
        requirement.key,
        {
          expectedGateVersion: review.gate.version,
          evidenceKind: "release_baseline",
          sourceGlobalId: baseline.globalId,
          sourceVersion: 1,
          sourceHash: baseline.snapshotHash,
        },
        { csrfToken, idempotencyKey, signal },
      ),
    ).resolves.toEqual(refreshed);

    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(
      `/projects/${review.project.globalId}/gates/${review.gate.globalId}/requirements/${requirement.key}/evidence`,
    );
    expect(init).toMatchObject({
      headers: { "Idempotency-Key": idempotencyKey },
      method: "POST",
      signal,
    });
    expect(options).toMatchObject({
      csrfToken,
      requireIdempotencyReplay: true,
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
    expect(options?.validate?.(evidence)).toBe(true);
    expect(request.mock.calls[1]?.[0]).toBe(
      `/projects/${review.project.globalId}/gates/${review.gate.globalId}/review`,
    );
  });

  it("loads the exact route with cancellation and strict response validation", async () => {
    const fixture = activeFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(fixture as T));
    const signal = new AbortController().signal;

    await expect(
      new LiveGateReviewDataSource(http).load(projectId, gateId, signal),
    ).resolves.toEqual(fixture);
    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(`/projects/${projectId}/gates/${gateId}/review`);
    expect(init).toEqual({ signal });
    expect(options).toMatchObject({
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
    expect(options?.validate?.(fixture)).toBe(true);
  });

  it.each([
    "gate.review.start",
    "gate.review.submit",
    "gate.review.exception.request",
    "gate.review.exception.decide",
    "gate.review.decide",
    "gate.review.reopen",
  ] as const)(
    "uses the exact receipt route and raw idempotency key for %s",
    async (operation) => {
      const receipt = {
        operation,
        status: "completed" as const,
        workspaceReloadRequired: true as const,
      };
      const http = new NpiHttpClient();
      const request = vi
        .spyOn(http, "request")
        .mockImplementation(<T>(): Promise<T> => Promise.resolve(receipt as T));
      const signal = new AbortController().signal;

      await expect(
        new LiveGateReviewDataSource(http).reconcileCommandReceipt(
          projectId,
          gateId,
          operation,
          { idempotencyKey, signal },
        ),
      ).resolves.toEqual(receipt);
      const [path, init, options] = request.mock.calls[0] ?? [];
      expect(path).toBe(
        `/projects/${projectId}/gates/${gateId}/review-command-receipts/${operation}`,
      );
      expect(init).toEqual({
        headers: { "Idempotency-Key": idempotencyKey },
        signal,
      });
      expect(new Request("https://npi.invalid", init).method).toBe("GET");
      expect(options).toMatchObject({
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
      });
      expect(options?.validate?.(receipt)).toBe(true);
    },
  );

  it("rejects an operation outside the closed receipt enum before transport", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");

    await expect(
      new LiveGateReviewDataSource(http).reconcileCommandReceipt(
        projectId,
        gateId,
        "gate.review.unknown" as "gate.review.start",
        {
          idempotencyKey,
          signal: new AbortController().signal,
        },
      ),
    ).rejects.toMatchObject({
      kind: "request_not_ready",
      referenceKind: "client",
    });
    expect(request).not.toHaveBeenCalled();
  });

  it.each(["completed", "absent"] as const)(
    "accepts the exact %s receipt over the private no-store GET boundary",
    async (status) => {
      const operation = "gate.review.decide" as const;
      const receipt = {
        operation,
        status,
        workspaceReloadRequired: true as const,
      };
      vi.stubGlobal(
        "fetch",
        vi.fn((_url: string | URL | Request, init?: RequestInit) => {
          const requestHeaders = new Headers(init?.headers);
          const requestId = requestHeaders.get("X-Request-ID");
          if (!requestId) throw new Error("The request ID is required.");
          return Promise.resolve(
            new Response(JSON.stringify(receipt), {
              status: 200,
              headers: {
                "Cache-Control": "private, no-store",
                "X-Request-ID": requestId,
                "X-Trace-ID": "trace-gate-review-receipt",
              },
            }),
          );
        }),
      );

      await expect(
        new LiveGateReviewDataSource().reconcileCommandReceipt(
          projectId,
          gateId,
          operation,
          {
            idempotencyKey,
            signal: new AbortController().signal,
          },
        ),
      ).resolves.toEqual(receipt);
      const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0] ?? [];
      expect(url).toBe(
        `/api/npi/v1/projects/${projectId}/gates/${gateId}/review-command-receipts/${operation}`,
      );
      expect(init?.method ?? "GET").toBe("GET");
      const headers = new Headers(init?.headers);
      expect(headers.get("Idempotency-Key")).toBe(idempotencyKey);
      expect(headers.has("X-Frappe-CSRF-Token")).toBe(false);
    },
  );

  it.each([
    {
      label: "an unknown status",
      receipt: {
        operation: "gate.review.decide",
        status: "pending",
        workspaceReloadRequired: true,
      },
    },
    {
      label: "an extra response property",
      receipt: {
        operation: "gate.review.decide",
        status: "completed",
        workspaceReloadRequired: true,
        traceId: "must-not-be-in-the-closed-body",
      },
    },
    {
      label: "a different operation",
      receipt: {
        operation: "gate.review.reopen",
        status: "completed",
        workspaceReloadRequired: true,
      },
    },
  ])("rejects $label in a receipt response", async ({ receipt }) => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string | URL | Request, init?: RequestInit) => {
        const requestHeaders = new Headers(init?.headers);
        const requestId = requestHeaders.get("X-Request-ID");
        if (!requestId) throw new Error("The request ID is required.");
        return Promise.resolve(
          new Response(JSON.stringify(receipt), {
            status: 200,
            headers: {
              "Cache-Control": "private, no-store",
              "X-Request-ID": requestId,
              "X-Trace-ID": "trace-gate-review-receipt",
            },
          }),
        );
      }),
    );

    await expect(
      new LiveGateReviewDataSource().reconcileCommandReceipt(
        projectId,
        gateId,
        "gate.review.decide",
        {
          idempotencyKey,
          signal: new AbortController().signal,
        },
      ),
    ).rejects.toMatchObject({
      kind: "invalid_response",
      referenceId: "trace-gate-review-receipt",
    });
  });

  it.each([
    undefined,
    "private",
    "no-store",
    "public, no-store",
    "private, no-store, max-age=0",
  ])("rejects a receipt cache policy of %s", async (cacheControl) => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string | URL | Request, init?: RequestInit) => {
        const requestHeaders = new Headers(init?.headers);
        const requestId = requestHeaders.get("X-Request-ID");
        if (!requestId) throw new Error("The request ID is required.");
        const headers: Record<string, string> = {
          "X-Request-ID": requestId,
          "X-Trace-ID": "trace-gate-review-receipt",
        };
        if (cacheControl !== undefined) {
          headers["Cache-Control"] = cacheControl;
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              operation: "gate.review.decide",
              status: "completed",
              workspaceReloadRequired: true,
            }),
            { status: 200, headers },
          ),
        );
      }),
    );

    await expect(
      new LiveGateReviewDataSource().reconcileCommandReceipt(
        projectId,
        gateId,
        "gate.review.decide",
        {
          idempotencyKey,
          signal: new AbortController().signal,
        },
      ),
    ).rejects.toMatchObject({
      kind: "invalid_response",
      referenceId: "trace-gate-review-receipt",
    });
  });

  it("uses all six exact command routes and closes every transport header", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const dataSource = new LiveGateReviewDataSource(http);
    const start: StartGateReviewCommand = {
      expectedGateVersion: 1,
      policyGlobalId: policyId,
      policyVersion: 1,
      policySnapshotHash: policyHash,
      bindings: [
        { slot: "technical_review", memberGlobalId: reviewerId },
        { slot: "decision_authority", memberGlobalId: decisionMemberId },
        { slot: "reopen_authority", memberGlobalId: reopenMemberId },
        { slot: "exception_authority", memberGlobalId: exceptionMemberId },
      ],
    };
    const submit: SubmitGateReviewCommand = {
      expectedCycleVersion: 1,
      expectedInputHash: inputHash,
      stepKey: "TECHNICAL_REVIEW",
      outcome: "approved",
      opinion: "Approved synthetic input.",
    };
    const requestException: RequestGateReviewExceptionCommand = {
      expectedCycleVersion: 1,
      expectedInputHash: inputHash,
      requirementGlobalId: requirementId,
      requirementKey: "DESIGN_BASELINE",
      kind: "controlled_deviation",
      reason: "Synthetic controlled reason.",
      risk: "Synthetic controlled risk.",
      expiresAt: "2026-08-01T10:03:00Z",
      closureActionGlobalId: closureActionId,
    };
    const decideException: DecideGateReviewExceptionCommand = {
      expectedCycleVersion: 2,
      expectedExceptionVersion: 1,
      expectedInputHash: inputHash,
      outcome: "approved",
      opinion: "Approved synthetic exception.",
    };
    const decide: DecideGateCommand = {
      expectedGateVersion: 1,
      expectedCycleVersion: 2,
      expectedInputHash: inputHash,
      outcome: "pass",
    };
    const reopen: ReopenGateCommand = {
      expectedGateVersion: 2,
      expectedCycleVersion: 3,
      expectedInputHash: inputHash,
      reason: "Reopen for an exact synthetic change.",
      policyGlobalId: policyId,
      policyVersion: 1,
      policySnapshotHash: policyHash,
      bindings: start.bindings,
    };
    const cases = [
      {
        body: start,
        invoke: () =>
          dataSource.startReview(projectId, gateId, start, context()),
        path: `/projects/${projectId}/gates/${gateId}:start-review`,
        response: withGateVersion(activeFixture(), 2),
      },
      {
        body: submit,
        invoke: () =>
          dataSource.submitReview(
            projectId,
            gateId,
            cycleId,
            submit,
            context(),
          ),
        path: `/projects/${projectId}/gates/${gateId}/review-cycles/${cycleId}/reviews`,
        response: submittedFixture(),
      },
      {
        body: requestException,
        invoke: () =>
          dataSource.requestException(
            projectId,
            gateId,
            cycleId,
            requestException,
            context(),
          ),
        path: `/projects/${projectId}/gates/${gateId}/review-cycles/${cycleId}/exceptions`,
        response: requestedExceptionFixture(),
      },
      {
        body: decideException,
        invoke: () =>
          dataSource.decideException(
            projectId,
            gateId,
            cycleId,
            exceptionId,
            decideException,
            context(),
          ),
        path: `/projects/${projectId}/gates/${gateId}/review-cycles/${cycleId}/exceptions/${exceptionId}:decide`,
        response: exceptionFixture(true),
      },
      {
        body: decide,
        invoke: () =>
          dataSource.decideGate(projectId, gateId, decide, context()),
        path: `/projects/${projectId}/gates/${gateId}:decide`,
        response: decidedFixture(),
      },
      {
        body: reopen,
        invoke: () =>
          dataSource.reopenGate(projectId, gateId, reopen, context()),
        path: `/projects/${projectId}/gates/${gateId}:reopen`,
        response: reopenedFixture(),
      },
    ] as const;

    for (const testCase of cases) {
      request.mockImplementationOnce(
        <T>(): Promise<T> => Promise.resolve(testCase.response as T),
      );
      await expect(testCase.invoke()).resolves.toEqual(testCase.response);
      const [path, init, options] = request.mock.calls.at(-1) ?? [];
      expect(path).toBe(testCase.path);
      expect(init).toMatchObject({
        body: JSON.stringify(testCase.body),
        headers: { "Idempotency-Key": idempotencyKey },
        method: "POST",
      });
      expect(options).toMatchObject({
        csrfToken,
        requireIdempotencyReplay: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
      });
      expect(options?.validate?.(testCase.response)).toBe(true);
    }
  });

  it.each([
    ["a nil route identity", projectId, "00000000-0000-0000-0000-000000000000"],
    ["a malformed route identity", "not-a-project", gateId],
  ])(
    "rejects %s before issuing a request",
    async (_label, candidateProjectId, candidateGateId) => {
      const http = new NpiHttpClient();
      const request = vi.spyOn(http, "request");
      await expect(
        new LiveGateReviewDataSource(http).load(
          candidateProjectId,
          candidateGateId,
          new AbortController().signal,
        ),
      ).rejects.toMatchObject({
        kind: "request_not_ready",
        referenceKind: "client",
      });
      expect(request).not.toHaveBeenCalled();
    },
  );

  it("rejects unsafe command preparation without sending credentials", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const dataSource = new LiveGateReviewDataSource(http);
    const invalidCommand = {
      expectedGateVersion: Number.MAX_SAFE_INTEGER,
      policyGlobalId: policyId,
      policyVersion: 1,
      policySnapshotHash: policyHash,
      bindings: [
        { slot: "technical_review", memberGlobalId: reviewerId },
        { slot: "technical_review", memberGlobalId: decisionMemberId },
      ],
    } as StartGateReviewCommand;

    await expect(
      dataSource.startReview(projectId, gateId, invalidCommand, context()),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    await expect(
      dataSource.startReview(
        projectId,
        gateId,
        {
          ...invalidCommand,
          expectedGateVersion: 1,
          bindings: [{ slot: "technical_review", memberGlobalId: reviewerId }],
        },
        {
          csrfToken: "short",
          idempotencyKey: "short",
          signal: new AbortController().signal,
        },
      ),
    ).rejects.toMatchObject({ kind: "request_not_ready" });
    expect(request).not.toHaveBeenCalled();
  });

  it("converts an aborted command transport into a cancellation result", async () => {
    const http = new NpiHttpClient();
    vi.spyOn(http, "request").mockImplementation(
      <T>(_path: string, init: RequestInit = {}): Promise<T> =>
        new Promise<T>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            reject(
              new NpiTransportError("network", "request-aborted", "request"),
            );
          });
        }),
    );
    const controller = new AbortController();
    const command: DecideGateCommand = {
      expectedGateVersion: 1,
      expectedCycleVersion: 1,
      expectedInputHash: inputHash,
      outcome: "pass",
    };
    const pending = new LiveGateReviewDataSource(http).decideGate(
      projectId,
      gateId,
      command,
      context(controller.signal),
    );

    controller.abort();
    await expect(pending).rejects.toBeInstanceOf(
      GateReviewRequestCancelledError,
    );
  });
});

describe("Gate review HTTP headers", () => {
  it("allows a normalized final colon action and validates the replay header", async () => {
    const requestId = "f1111111-1111-4111-8111-111111111111";
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ accepted: true }), {
            status: 200,
            headers: {
              "Idempotency-Replayed": "false",
              "X-Request-ID": requestId,
              "X-Trace-ID": "trace-gate-review",
            },
          }),
        ),
      ),
    );

    await expect(
      new NpiHttpClient().request(
        `/projects/${projectId}/gates/${gateId}:decide`,
        {
          headers: {
            "Idempotency-Key": idempotencyKey,
            "X-Request-ID": requestId,
          },
          method: "POST",
        },
        {
          csrfToken,
          requireIdempotencyReplay: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
        },
      ),
    ).resolves.toEqual({ accepted: true });
    const [url, request] = vi.mocked(globalThis.fetch).mock.calls[0] ?? [];
    expect(url).toBe(
      `/api/npi/v1/projects/${projectId}/gates/${gateId}:decide`,
    );
    const headers = new Headers(request?.headers);
    expect(headers.get("Idempotency-Key")).toBe(idempotencyKey);
    expect(headers.get("X-Frappe-CSRF-Token")).toBe(csrfToken);
  });

  it.each([undefined, "FALSE", "replayed"])(
    "rejects a required invalid replay header %s",
    async (replayed) => {
      const requestId = "f1111111-1111-4111-8111-111111111111";
      const headers: Record<string, string> = {
        "X-Request-ID": requestId,
        "X-Trace-ID": "trace-gate-review",
      };
      if (replayed !== undefined) headers["Idempotency-Replayed"] = replayed;
      vi.stubGlobal(
        "fetch",
        vi.fn(() =>
          Promise.resolve(
            new Response(JSON.stringify({ accepted: true }), {
              status: 200,
              headers,
            }),
          ),
        ),
      );

      await expect(
        new NpiHttpClient().request(
          `/projects/${projectId}/gates/${gateId}:decide`,
          {
            headers: { "X-Request-ID": requestId },
            method: "POST",
          },
          {
            csrfToken,
            requireIdempotencyReplay: true,
            requireRequestIdEcho: true,
            requireTraceId: true,
          },
        ),
      ).rejects.toMatchObject({
        kind: "invalid_response",
        referenceId: "trace-gate-review",
      });
    },
  );

  it("preserves a closed problem response when a failed command has no success-only replay header", async () => {
    const requestId = "f1111111-1111-4111-8111-111111111111";
    const problem = {
      type: "urn:npi:error:validation",
      title: "The request failed validation.",
      status: 422,
      code: "VALIDATION_FAILED",
      traceId: "trace-gate-review",
      retryable: false,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(problem), {
            status: 422,
            headers: {
              "X-Request-ID": requestId,
              "X-Trace-ID": problem.traceId,
            },
          }),
        ),
      ),
    );

    const failure = await new NpiHttpClient()
      .request(
        `/projects/${projectId}/gates/${gateId}:decide`,
        {
          headers: { "X-Request-ID": requestId },
          method: "POST",
        },
        {
          csrfToken,
          requireIdempotencyReplay: true,
          requireRequestIdEcho: true,
          requireTraceId: true,
        },
      )
      .catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(NpiApiError);
    expect((failure as NpiApiError).problem).toEqual(problem);
  });
});
