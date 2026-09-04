import type {
  GateDecisionSummaryViewModel,
  GateReviewExceptionViewModel,
  GateReviewSelectedStepViewModel,
  GateReviewViewModel,
} from "../../src/domain/view-models";
import { gateEvidenceFixture } from "./gate-evidence-fixture";

export const gateReviewFixtureIds = {
  cycle: "45454545-4545-4545-8545-454545454545",
  successorCycle: "46464646-4646-4646-8646-464646464646",
  decision: "56565656-5656-4565-8565-565656565656",
  exception: "67676767-6767-4676-8676-676767676767",
  policy: "78787878-7878-4787-8787-787878787878",
  closureAction: "89898989-8989-4898-8989-898989898989",
  unrelatedClosureAction: "8a8a8a8a-8a8a-4a8a-8a8a-8a8a8a8a8a8a",
  engineeringMember: "91919191-9191-4919-8919-919191919191",
  toolingMember: "92929292-9292-4929-8929-929292929292",
  qualityMember: "93939393-9393-4939-8939-939393939393",
  decisionMember: "94949494-9494-4949-8949-949494949494",
  reopenMember: "95959595-9595-4959-8959-959595959595",
  exceptionMember: "96969696-9696-4969-8969-969696969696",
} as const;

const inputHash = "5".repeat(64);
const policyHash = "6".repeat(64);

function member(
  memberGlobalId: string,
  userId: string,
  displayName: string,
): GateReviewViewModel["eligibleMembers"][number] {
  return { displayName, memberGlobalId, userId };
}

const engineeringMember = member(
  gateReviewFixtureIds.engineeringMember,
  "reviewer@example.invalid",
  "Synthetic Engineering Reviewer",
);
const toolingMember = member(
  gateReviewFixtureIds.toolingMember,
  "tooling.reviewer@example.invalid",
  "Synthetic Tooling Reviewer",
);
const qualityMember = member(
  gateReviewFixtureIds.qualityMember,
  "quality.reviewer@example.invalid",
  "Synthetic Quality Reviewer",
);
const decisionMember = member(
  gateReviewFixtureIds.decisionMember,
  "decision.authority@example.invalid",
  "Synthetic Decision Authority",
);
const reopenMember = member(
  gateReviewFixtureIds.reopenMember,
  "reopen.authority@example.invalid",
  "Synthetic Reopen Authority",
);
const exceptionMember = member(
  gateReviewFixtureIds.exceptionMember,
  "exception.authority@example.invalid",
  "Synthetic Exception Authority",
);

function selectedSteps(): readonly GateReviewSelectedStepViewModel[] {
  return [
    {
      assignedMember: engineeringMember,
      review: null,
      sequence: 1,
      slot: "engineering_review",
      state: "available",
      stepKey: "ENGINEERING_REVIEW",
    },
    {
      assignedMember: toolingMember,
      review: {
        actor: toolingMember.userId,
        globalId: "97979797-9797-4979-8979-979797979797",
        inputHash,
        opinion: "The tooling input is acceptable for this synthetic review.",
        outcome: "approved",
        reviewedAt: "2026-07-24T10:04:00Z",
        snapshotHash: "7".repeat(64),
        stepKey: "TOOLING_REVIEW",
      },
      sequence: 1,
      slot: "tooling_review",
      state: "approved",
      stepKey: "TOOLING_REVIEW",
    },
    {
      assignedMember: qualityMember,
      review: null,
      sequence: 2,
      slot: "quality_review",
      state: "waiting",
      stepKey: "QUALITY_REVIEW",
    },
  ];
}

function reviewPolicy(): GateReviewViewModel["availablePolicies"][number] {
  return {
    authoritySlots: [
      { purpose: "review", slot: "engineering_review" },
      { purpose: "review", slot: "tooling_review" },
      { purpose: "review", slot: "quality_review" },
      { purpose: "decision", slot: "decision_authority" },
      { purpose: "reopen", slot: "reopen_authority" },
      { purpose: "exception", slot: "exception_authority" },
    ],
    exceptionRules: [
      {
        approvalAuthoritySlot: "exception_authority",
        eligibleRequirementKeys: ["CUSTOMER_CONFIRMATION"],
        kind: "controlled_deviation",
        maximumValidityDays: 30,
        requiredClosureActionKind: "action",
      },
    ],
    policyRef: {
      globalId: gateReviewFixtureIds.policy,
      snapshotHash: policyHash,
      version: 1,
    },
  };
}

export function gateReviewFixture(
  overrides: Partial<GateReviewViewModel> = {},
): GateReviewViewModel {
  const evidence = gateEvidenceFixture();
  const fixture: GateReviewViewModel = {
    activeCycle: {
      bindings: [
        {
          displayName: engineeringMember.displayName,
          memberGlobalId: engineeringMember.memberGlobalId,
          slot: "engineering_review",
          userId: engineeringMember.userId,
        },
        {
          displayName: toolingMember.displayName,
          memberGlobalId: toolingMember.memberGlobalId,
          slot: "tooling_review",
          userId: toolingMember.userId,
        },
        {
          displayName: qualityMember.displayName,
          memberGlobalId: qualityMember.memberGlobalId,
          slot: "quality_review",
          userId: qualityMember.userId,
        },
        {
          displayName: decisionMember.displayName,
          memberGlobalId: decisionMember.memberGlobalId,
          slot: "decision_authority",
          userId: decisionMember.userId,
        },
        {
          displayName: reopenMember.displayName,
          memberGlobalId: reopenMember.memberGlobalId,
          slot: "reopen_authority",
          userId: reopenMember.userId,
        },
        {
          displayName: exceptionMember.displayName,
          memberGlobalId: exceptionMember.memberGlobalId,
          slot: "exception_authority",
          userId: exceptionMember.userId,
        },
      ],
      exceptions: [],
      globalId: gateReviewFixtureIds.cycle,
      inputHash,
      number: 1,
      policyRef: {
        globalId: gateReviewFixtureIds.policy,
        snapshotHash: policyHash,
        version: 1,
      },
      policyDefinition: reviewPolicy(),
      selectedSteps: selectedSteps(),
      startedAt: "2026-07-24T10:00:00Z",
      startedBy: "review.manager@example.invalid",
      state: "active",
      trigger: "manual_start",
      version: 4,
    },
    availablePolicies: [reviewPolicy()],
    blockers: [
      {
        dueAt: "2026-08-02T12:00:00Z",
        globalId: "98989898-9898-4989-8989-989898989898",
        kind: "issue",
        owner: "issue.owner@example.invalid",
        state: "open",
        stateLabelSource: "Open",
        title: "Synthetic unresolved dimensional issue",
      },
    ],
    dependencyChanges: [],
    decisionReadiness: {
      allowedOutcomes: [],
      blockedReasons: [
        {
          code: "DECISION_AUTHORITY_REQUIRED",
          outcome: "pass",
        },
        {
          code: "DECISION_AUTHORITY_REQUIRED",
          outcome: "conditional_pass",
        },
        {
          code: "DECISION_AUTHORITY_REQUIRED",
          outcome: "reject",
        },
      ],
    },
    decisions: [],
    eligibleClosureActions: [
      {
        globalId: gateReviewFixtureIds.closureAction,
        state: "open",
        stateLabelSource: "Open",
        title: "Close the synthetic controlled deviation",
        version: 2,
      },
      {
        globalId: gateReviewFixtureIds.unrelatedClosureAction,
        state: "open",
        stateLabelSource: "Open",
        title: "Unrelated synthetic closure action",
        version: 1,
      },
    ],
    eligibleMembers: [
      engineeringMember,
      toolingMember,
      qualityMember,
      decisionMember,
      reopenMember,
      exceptionMember,
    ],
    evidence,
    exceptionRequestOptions: [],
    gate: {
      currentCycleGlobalId: gateReviewFixtureIds.cycle,
      downstreamDecisionCurrent: false,
      globalId: evidence.gate.globalId,
      key: evidence.gate.key,
      latestDecisionGlobalId: null,
      latestDecisionHash: null,
      latestDecisionOutcome: null,
      reviewState: "in_review",
      title: evidence.gate.title,
      version: evidence.gate.version,
    },
    permissions: {
      canApproveException: false,
      canDecide: false,
      canRequestException: false,
      canReopen: false,
      canReview: true,
      canStartReview: false,
      canView: true,
    },
    project: evidence.project,
  };
  return { ...fixture, ...overrides };
}

export function gateReviewNoCycleFixture(): GateReviewViewModel {
  const fixture = gateReviewFixture();
  return {
    ...fixture,
    activeCycle: null,
    blockers: [],
    decisionReadiness: {
      allowedOutcomes: [],
      blockedReasons: [
        { code: "REVIEW_CYCLE_CLOSED", outcome: "pass" },
        { code: "REVIEW_CYCLE_CLOSED", outcome: "conditional_pass" },
        { code: "REVIEW_CYCLE_CLOSED", outcome: "reject" },
      ],
    },
    gate: {
      ...fixture.gate,
      currentCycleGlobalId: null,
      reviewState: "not_started",
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

export function gateReviewReadOnlyFixture(): GateReviewViewModel {
  const fixture = gateReviewFixture();
  return {
    ...fixture,
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

export function gateReviewExceptionEligibleFixture(): GateReviewViewModel {
  const fixture = gateReviewFixture();
  const evidence: GateReviewViewModel["evidence"] = {
    ...fixture.evidence,
    requirements: fixture.evidence.requirements.map((requirement) => {
      if (requirement.key === "DIMENSIONAL_REPORT") {
        return {
          ...requirement,
          evidence: requirement.evidence.map((reference) => ({
            ...reference,
            ...(reference.file
              ? {
                  file: {
                    ...reference.file,
                    scanState: "clean" as const,
                  },
                }
              : {}),
          })),
          evidenceState: "scan_clean",
        };
      }
      if (requirement.key === "CUSTOMER_CONFIRMATION") {
        return {
          ...requirement,
          classification: "required",
        };
      }
      return requirement;
    }),
    summary: {
      evidenceCount: 2,
      missingRequiredCount: 1,
      requiredCount: 3,
      unsafeScanCount: 0,
    },
  };
  const requirement = evidence.requirements.find(
    (candidate) => candidate.key === "CUSTOMER_CONFIRMATION",
  );
  if (!requirement) throw new Error("The fixture requires a requirement.");
  return {
    ...fixture,
    evidence,
    exceptionRequestOptions: [
      {
        closureActionGlobalIds: [gateReviewFixtureIds.closureAction],
        kind: "controlled_deviation",
        maximumValidityDays: 30,
        requirementGlobalId: requirement.globalId,
        requirementKey: requirement.key,
      },
    ],
    permissions: {
      ...fixture.permissions,
      canRequestException: true,
    },
  };
}

export function gateReviewDecisionReadyFixture(): GateReviewViewModel {
  const fixture = gateReviewFixture();
  if (!fixture.activeCycle) throw new Error("The fixture requires a cycle.");
  const evidence: GateReviewViewModel["evidence"] = {
    ...fixture.evidence,
    requirements: fixture.evidence.requirements.map((requirement) =>
      requirement.key === "DIMENSIONAL_REPORT"
        ? {
            ...requirement,
            evidence: requirement.evidence.map((reference) => ({
              ...reference,
              ...(reference.file
                ? {
                    file: {
                      ...reference.file,
                      scanState: "clean" as const,
                    },
                  }
                : {}),
            })),
            evidenceState: "scan_clean",
          }
        : requirement,
    ),
    summary: {
      ...fixture.evidence.summary,
      unsafeScanCount: 0,
    },
  };
  const completedSteps = fixture.activeCycle.selectedSteps.map(
    (step, index): GateReviewSelectedStepViewModel => ({
      ...step,
      review: {
        actor: step.assignedMember.userId,
        globalId:
          index === 0
            ? "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1"
            : index === 1
              ? "a2a2a2a2-a2a2-4a2a-8a2a-a2a2a2a2a2a2"
              : "a3a3a3a3-a3a3-4a3a-8a3a-a3a3a3a3a3a3",
        inputHash,
        opinion: "Approved for the synthetic decision-ready fixture.",
        outcome: "approved",
        reviewedAt: `2026-07-24T10:0${String(index + 4)}:00Z`,
        snapshotHash: String(index + 7).repeat(64),
        stepKey: step.stepKey,
      },
      state: "approved",
    }),
  );
  return {
    ...fixture,
    activeCycle: {
      ...fixture.activeCycle,
      selectedSteps: completedSteps,
      version: 6,
    },
    blockers: [],
    decisionReadiness: {
      allowedOutcomes: ["pass", "reject"],
      blockedReasons: [
        {
          code: "EXCEPTION_NOT_REQUIRED",
          outcome: "conditional_pass",
        },
      ],
    },
    evidence,
    permissions: {
      ...fixture.permissions,
      canDecide: true,
      canRequestException: false,
      canReview: false,
    },
  };
}

function decisionSummary(current: boolean): GateDecisionSummaryViewModel {
  const fixture = gateReviewDecisionReadyFixture();
  const cycle = fixture.activeCycle;
  if (!cycle) throw new Error("The fixture requires a cycle.");
  const requirements = fixture.evidence.requirements.map(
    (requirement, index) => ({
      evidenceComplete:
        requirement.classification !== "required" ||
        (requirement.evidence.length > 0 &&
          requirement.evidence.every(
            (reference) =>
              !reference.file || reference.file.scanState === "clean",
          )),
      globalId: requirement.globalId,
      priority: requirement.priority,
      requirementKey: requirement.key,
      sourceHash: String.fromCharCode(100 + index).repeat(64),
      sourceVersion: 1,
    }),
  );
  const frozenEvidence = fixture.evidence.requirements
    .flatMap((requirement) =>
      requirement.evidence.map((reference) => ({
        evidenceKind: reference.kind,
        fileSafe: !reference.file || reference.file.scanState === "clean",
        globalId: reference.globalId,
        isFile: reference.kind === "file_revision",
        requirementGlobalId: requirement.globalId,
        sourceGlobalId: reference.sourceGlobalId,
        sourceHash: reference.objectHash,
        sourceVersion: reference.revision,
      })),
    )
    .sort((left, right) => left.globalId.localeCompare(right.globalId));
  return {
    current,
    cycleGlobalId: gateReviewFixtureIds.cycle,
    decidedAt: "2026-07-24T10:15:00Z",
    decidedBy: decisionMember.userId,
    detail: {
      cycleNumber: cycle.number,
      cycleVersion: cycle.version,
      exceptionHashes: [],
      inputSnapshot: {
        blockers: [],
        dependencies: [
          {
            globalId: fixture.evidence.gate.globalId,
            kind: "gate_input_snapshot" as const,
            snapshotHash: fixture.evidence.gate.requirementSnapshotHash,
            version: fixture.evidence.gate.version,
          },
          ...frozenEvidence.map((reference) => ({
            globalId: reference.globalId,
            kind: "gate_input_snapshot" as const,
            snapshotHash: reference.sourceHash,
            version: reference.sourceVersion,
          })),
        ].sort((left, right) => left.globalId.localeCompare(right.globalId)),
        evidence: frozenEvidence,
        gateGlobalId: fixture.evidence.gate.globalId,
        gateVersion: fixture.evidence.gate.version,
        projectGlobalId: fixture.evidence.project.globalId,
        requirements,
        schemaVersion: 1,
        tenantId: "synthetic-tenant",
      },
      lineageHash: "d".repeat(64),
      policyRef: cycle.policyRef,
      reviewHashes: cycle.selectedSteps.flatMap((step) =>
        step.review ? [step.review.snapshotHash] : [],
      ),
    },
    globalId: gateReviewFixtureIds.decision,
    inputHash,
    outcome: "pass",
    snapshotHash: "a".repeat(64),
  };
}

export function gateReviewDecidedFixture(): GateReviewViewModel {
  const fixture = gateReviewDecisionReadyFixture();
  if (!fixture.activeCycle) throw new Error("The fixture requires a cycle.");
  return {
    ...fixture,
    activeCycle: {
      ...fixture.activeCycle,
      state: "decided",
      version: 7,
    },
    decisions: [decisionSummary(true)],
    decisionReadiness: {
      allowedOutcomes: [],
      blockedReasons: [
        { code: "REVIEW_CYCLE_CLOSED", outcome: "pass" },
        { code: "REVIEW_CYCLE_CLOSED", outcome: "conditional_pass" },
        { code: "REVIEW_CYCLE_CLOSED", outcome: "reject" },
      ],
    },
    gate: {
      ...fixture.gate,
      downstreamDecisionCurrent: true,
      latestDecisionGlobalId: gateReviewFixtureIds.decision,
      latestDecisionHash: "a".repeat(64),
      latestDecisionOutcome: "pass",
      reviewState: "decided",
    },
    permissions: {
      canApproveException: false,
      canDecide: false,
      canRequestException: false,
      canReopen: true,
      canReview: false,
      canStartReview: false,
      canView: true,
    },
  };
}

export function gateReviewRequiresReviewFixture(): GateReviewViewModel {
  const fixture = gateReviewDecidedFixture();
  if (!fixture.activeCycle) throw new Error("The fixture requires a cycle.");
  const newInputHash = "c".repeat(64);
  return {
    ...fixture,
    activeCycle: {
      ...fixture.activeCycle,
      globalId: gateReviewFixtureIds.successorCycle,
      inputHash: newInputHash,
      number: 2,
      selectedSteps: fixture.activeCycle.selectedSteps.map((step) => ({
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
      {
        actorUserId: "npi-gate-review-dependency-system",
        eventGlobalId: "a4a4a4a4-a4a4-4a4a-8a4a-a4a4a4a4a4a4",
        eventType: "invalidated",
        initiatedByUserId: "source.owner@example.invalid",
        newInputHash,
        occurredAt: "2026-07-24T10:20:00Z",
        oldInputHash: inputHash,
        priorCycleGlobalId: gateReviewFixtureIds.cycle,
        priorDecisionGlobalId: gateReviewFixtureIds.decision,
        priorDecisionLineageHash: "d".repeat(64),
        reason: "GATE_SOURCE_CHANGED",
        successorCycleGlobalId: gateReviewFixtureIds.successorCycle,
        impactActionGlobalId: null,
      },
    ],
    gate: {
      ...fixture.gate,
      currentCycleGlobalId: gateReviewFixtureIds.successorCycle,
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

export function pendingExceptionFixture(): GateReviewExceptionViewModel {
  const evidence = gateEvidenceFixture();
  const requirement = evidence.requirements.find(
    (candidate) => candidate.key === "CUSTOMER_CONFIRMATION",
  );
  if (!requirement) throw new Error("The fixture requires a requirement.");
  return {
    allowedOutcomes: [],
    closureActionRef: {
      globalId: gateReviewFixtureIds.closureAction,
      snapshotHash: "e".repeat(64),
      version: 2,
    },
    decision: null,
    expiresAt: "2026-08-12T23:59:59Z",
    globalId: gateReviewFixtureIds.exception,
    kind: "controlled_deviation",
    reason: "A bounded synthetic exception is required.",
    requestSchemaVersion: 2,
    requestSnapshotHash: "b".repeat(64),
    requestedAt: "2026-07-24T10:10:00Z",
    requester: engineeringMember,
    requirementGlobalId: requirement.globalId,
    requirementKey: requirement.key,
    risk: "The synthetic deviation remains visible until closure.",
    state: "pending",
    version: 1,
  };
}

export function gateReviewPendingExceptionFixture(): GateReviewViewModel {
  const fixture = gateReviewExceptionEligibleFixture();
  return {
    ...fixture,
    activeCycle: fixture.activeCycle
      ? {
          ...fixture.activeCycle,
          exceptions: [
            {
              ...pendingExceptionFixture(),
              allowedOutcomes: ["approved", "rejected"],
            },
          ],
          version: fixture.activeCycle.version + 1,
        }
      : null,
    exceptionRequestOptions: [],
    permissions: {
      canApproveException: true,
      canDecide: false,
      canRequestException: false,
      canReopen: false,
      canReview: false,
      canStartReview: false,
      canView: true,
    },
  };
}

export function gateReviewExceptionHistoryFixture(): GateReviewViewModel {
  const fixture = gateReviewExceptionEligibleFixture();
  if (!fixture.activeCycle) throw new Error("The fixture requires a cycle.");
  const exception = pendingExceptionFixture();
  return {
    ...fixture,
    activeCycle: {
      ...fixture.activeCycle,
      exceptions: [
        {
          ...exception,
          decision: {
            approver: exceptionMember,
            decidedAt: "2026-07-24T10:12:00Z",
            opinion: "The bounded synthetic exception is approved.",
            outcome: "approved",
            snapshotHash: "f".repeat(64),
          },
          state: "approved",
          version: 2,
        },
      ],
      version: fixture.activeCycle.version + 2,
    },
    exceptionRequestOptions: [],
    permissions: {
      ...fixture.permissions,
      canApproveException: false,
      canRequestException: false,
    },
  };
}

export function gateReviewReopenedFixture(): GateReviewViewModel {
  const fixture = gateReviewDecidedFixture();
  if (!fixture.activeCycle) throw new Error("The fixture requires a cycle.");
  return {
    ...fixture,
    activeCycle: {
      ...fixture.activeCycle,
      globalId: gateReviewFixtureIds.successorCycle,
      number: fixture.activeCycle.number + 1,
      selectedSteps: fixture.activeCycle.selectedSteps.map((step) => ({
        ...step,
        review: null,
        state:
          step.sequence === 1 ? ("available" as const) : ("waiting" as const),
      })),
      state: "active",
      trigger: "manual_reopen",
      version: 1,
    },
    decisions: fixture.decisions.map((decision) => ({
      ...decision,
      current: false,
    })),
    gate: {
      ...fixture.gate,
      currentCycleGlobalId: gateReviewFixtureIds.successorCycle,
      downstreamDecisionCurrent: false,
      reviewState: "in_review",
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
