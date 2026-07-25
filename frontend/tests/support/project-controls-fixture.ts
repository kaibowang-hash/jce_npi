import type {
  ProjectActivityPageViewModel,
  ProjectControlsViewModel,
  ProjectLearningPageViewModel,
} from "../../src/domain/view-models";

export const projectControlIds = {
  project: "11111111-1111-4111-8111-111111111111",
  policy: "22222222-2222-4222-8222-222222222222",
  policyVersion: "33333333-3333-4333-8333-333333333333",
  binding: "44444444-4444-4444-8444-444444444444",
  managerMember: "55555555-5555-4555-8555-555555555555",
  qualityMember: "66666666-6666-4666-8666-666666666666",
  assessment: "77777777-7777-4777-8777-777777777777",
  comment: "88888888-8888-4888-8888-888888888888",
  fileRevision: "99999999-9999-4999-8999-999999999999",
  gate: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  learning: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  template: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
} as const;

const snapshotHash = "a".repeat(64);
const fileHash = "b".repeat(64);

export function projectControlsFixture(): ProjectControlsViewModel {
  return {
    project: {
      globalId: projectControlIds.project,
      businessCode: "NPI-26018",
      title: "Battery housing",
      state: "active",
      version: 7,
      tenantId: "acme",
    },
    policy: {
      globalId: projectControlIds.policy,
      code: "PCP-STD",
      version: 3,
      snapshotHash,
      title: "Standard project control policy",
      healthAssessmentSlot: "quality_lead",
    },
    binding: {
      globalId: projectControlIds.binding,
      version: 2,
      authorities: [
        {
          slot: "project_manager",
          memberGlobalId: projectControlIds.managerMember,
          userId: "manager@example.invalid",
          displayName: "Project Manager",
        },
        {
          slot: "quality_lead",
          memberGlobalId: projectControlIds.qualityMember,
          userId: "quality@example.invalid",
          displayName: "Quality Lead",
        },
      ],
    },
    bindingOptions: {
      policies: [
        {
          policyRef: {
            globalId: projectControlIds.policy,
            version: 3,
            snapshotHash,
          },
          code: "PCP-STD",
          title: "Standard project control policy",
          authoritySlots: ["project_manager", "quality_lead"],
        },
      ],
      eligibleMembers: [
        {
          memberGlobalId: projectControlIds.managerMember,
          userId: "manager@example.invalid",
          displayName: "Project Manager",
        },
        {
          memberGlobalId: projectControlIds.qualityMember,
          userId: "quality@example.invalid",
          displayName: "Quality Lead",
        },
      ],
    },
    health: {
      overallStatus: "yellow",
      dimensions: [
        {
          dimension: "progress",
          ruleMode: "higher_is_better",
          status: "yellow",
          numericValue: "82.5",
        },
        {
          dimension: "cost",
          ruleMode: "unavailable",
          status: "unavailable",
          numericValue: null,
        },
        {
          dimension: "quality",
          ruleMode: "manual",
          status: "green",
          numericValue: null,
        },
        {
          dimension: "risk",
          ruleMode: "manual",
          status: "yellow",
          numericValue: null,
        },
      ],
      assessment: {
        globalId: projectControlIds.assessment,
        assessedAt: "2026-07-25T10:00:00Z",
        actor: {
          slot: "quality_lead",
          memberGlobalId: projectControlIds.qualityMember,
          userId: "quality@example.invalid",
          displayName: "Quality Lead",
        },
        reason: null,
        recoveryPlan: null,
      },
    },
    lifecycleActions: [
      {
        action: "pause",
        available: true,
        targetState: "on_hold",
        authoritySlot: "project_manager",
        reasonCode: "available",
        prerequisites: [],
      },
      {
        action: "cancel",
        available: false,
        targetState: "cancelled",
        authoritySlot: "project_manager",
        reasonCode: "authority_required",
        prerequisites: [],
      },
      {
        action: "resume",
        available: false,
        targetState: "active",
        authoritySlot: null,
        reasonCode: "transition_not_defined",
        prerequisites: [],
      },
      {
        action: "complete",
        available: false,
        targetState: "completed",
        authoritySlot: "project_manager",
        reasonCode: "prerequisite_unavailable",
        prerequisites: [
          { key: "controlled_files", status: "satisfied" },
          { key: "cost", status: "unavailable" },
          { key: "handover", status: "unavailable" },
          { key: "open_blockers", status: "satisfied" },
        ],
      },
    ],
    permissions: {
      canBindPolicy: true,
      canAssessHealth: true,
      canTransition: true,
    },
  };
}

export function projectActivityFixture(): ProjectActivityPageViewModel {
  return {
    projectId: projectControlIds.project,
    items: [
      {
        globalId: projectControlIds.comment,
        eventType: "comment_added",
        actorUserId: "manager@example.invalid",
        occurredAt: "2026-07-25T11:00:00Z",
        detail: {
          body: "Review the controlled Gate evidence.",
          mentions: [
            {
              memberGlobalId: projectControlIds.qualityMember,
              userId: "quality@example.invalid",
              displayName: "Quality Lead",
            },
          ],
          attachments: [
            {
              globalId: projectControlIds.fileRevision,
              version: 4,
              fileName: "trial-report.pdf",
              mimeType: "application/pdf",
              sizeBytes: 4096,
              sha256: fileHash,
              scanState: "clean",
            },
          ],
          objectLinks: [
            {
              type: "gate",
              globalId: projectControlIds.gate,
              version: 3,
              code: "G3",
              title: "Tooling release",
              target: {
                kind: "gate",
                projectId: projectControlIds.project,
                gateId: projectControlIds.gate,
              },
            },
          ],
        },
      },
    ],
    nextCursor: null,
    permissions: {
      canComment: true,
      canFollow: true,
    },
    following: true,
    followerVersion: 2,
    commentOptions: {
      truncated: false,
      mentions: [
        {
          memberGlobalId: projectControlIds.qualityMember,
          userId: "quality@example.invalid",
          displayName: "Quality Lead",
        },
      ],
      attachments: [
        {
          globalId: projectControlIds.fileRevision,
          version: 4,
          fileName: "trial-report.pdf",
          mimeType: "application/pdf",
          sizeBytes: 4096,
          sha256: fileHash,
          scanState: "clean",
        },
      ],
      objectLinks: [
        {
          type: "gate",
          globalId: projectControlIds.gate,
          version: 3,
          code: "G3",
          title: "Tooling release",
          target: {
            kind: "gate",
            projectId: projectControlIds.project,
            gateId: projectControlIds.gate,
          },
        },
      ],
    },
  };
}

export function projectLearningFixture(): ProjectLearningPageViewModel {
  return {
    projectId: projectControlIds.project,
    permissions: {
      canCreate: true,
    },
    items: [
      {
        globalId: projectControlIds.learning,
        projectGlobalId: projectControlIds.project,
        kind: "retrospective",
        title: "Hot runner sourcing retrospective",
        content: "Supplier lead-time evidence must be captured before G2.",
        recommendation: "Add a sourcing evidence requirement to the template.",
        tags: ["supplier", "lead-time"],
        templateRef: {
          globalId: projectControlIds.template,
          version: 5,
          snapshotHash,
        },
        createdBy: "manager@example.invalid",
        createdAt: "2026-07-25T12:00:00Z",
        version: 1,
        target: {
          kind: "project_learning",
          projectId: projectControlIds.project,
          learningId: projectControlIds.learning,
        },
      },
    ],
  };
}
