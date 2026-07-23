import type {
  DomainWorkItemPageViewModel,
  ProjectWorkContextViewModel,
  ProjectWorkPolicyReference,
} from "../../src/domain/view-models";
import { projectCockpitFixture } from "./project-fixture";

export const projectWorkProjectVersion = 4;

export function projectWorkCockpitFixture() {
  return projectCockpitFixture({ version: projectWorkProjectVersion });
}

export const projectWorkPolicyFixture: ProjectWorkPolicyReference = {
  globalId: "60000000-0000-4000-8000-000000000001",
  version: 1,
  snapshotHash:
    "1111111111111111111111111111111111111111111111111111111111111111",
};

export function projectWorkContextFixture(): ProjectWorkContextViewModel {
  const projectId = projectWorkCockpitFixture().project.globalId;
  const rootWbsId = "70000000-0000-4000-8000-000000000001";
  const childWbsId = "70000000-0000-4000-8000-000000000002";
  const engineeringMemberId = "61000000-0000-4000-8000-000000000001";
  const qualityMemberId = "61000000-0000-4000-8000-000000000002";
  const substituteMemberId = "61000000-0000-4000-8000-000000000003";
  const engineeringRoleId = "62000000-0000-4000-8000-000000000001";
  const qualityRoleId = "62000000-0000-4000-8000-000000000002";
  const toolingRoleId = "62000000-0000-4000-8000-000000000003";
  const baselineId = "72000000-0000-4000-8000-000000000001";
  return {
    projectId,
    projectVersion: projectWorkProjectVersion,
    initialized: true,
    workPolicyRef: projectWorkPolicyFixture,
    members: [
      {
        globalId: engineeringMemberId,
        projectId,
        userId: "engineering.lead@example.invalid",
        effectiveFrom: "2026-07-23",
        version: 1,
      },
      {
        globalId: qualityMemberId,
        projectId,
        userId: "quality.lead@example.invalid",
        effectiveFrom: "2026-07-23",
        effectiveTo: "2026-12-31",
        version: 1,
      },
      {
        globalId: substituteMemberId,
        projectId,
        userId: "tooling.lead@example.invalid",
        effectiveFrom: "2026-07-23",
        version: 1,
      },
    ],
    roleAssignments: [
      {
        globalId: engineeringRoleId,
        projectId,
        memberId: engineeringMemberId,
        roleKey: "engineering.lead",
        effectiveFrom: "2026-07-23",
        version: 1,
      },
      {
        globalId: qualityRoleId,
        projectId,
        memberId: qualityMemberId,
        roleKey: "quality.lead",
        effectiveFrom: "2026-07-23",
        effectiveTo: "2026-12-31",
        version: 1,
      },
      {
        globalId: toolingRoleId,
        projectId,
        memberId: substituteMemberId,
        roleKey: "tooling.lead",
        effectiveFrom: "2026-07-23",
        version: 1,
      },
    ],
    substitutions: [
      {
        globalId: "63000000-0000-4000-8000-000000000001",
        projectId,
        roleAssignmentId: qualityRoleId,
        substituteMemberId,
        effectiveFrom: "2026-08-01",
        effectiveTo: "2026-08-15",
        version: 1,
      },
    ],
    raciAssignments: [
      {
        globalId: "64000000-0000-4000-8000-000000000001",
        projectId,
        contextType: "project",
        contextId: projectId,
        responsibilityKey: "project.delivery",
        roleAssignmentId: engineeringRoleId,
        raci: "responsible",
        version: 1,
      },
      {
        globalId: "64000000-0000-4000-8000-000000000002",
        projectId,
        contextType: "wbs_item",
        contextId: childWbsId,
        responsibilityKey: "design.review",
        roleAssignmentId: qualityRoleId,
        raci: "accountable",
        version: 1,
      },
    ],
    wbsItems: [
      {
        globalId: rootWbsId,
        projectId,
        code: "1",
        title: "Synthetic tooling launch",
        ownerRoleAssignmentId: engineeringRoleId,
        plannedStart: "2026-07-25",
        plannedFinish: "2026-08-10",
        milestone: false,
        statusKey: "not_started",
        statusLabelSource: "Not started",
        progressPercent: 0,
        critical: true,
        version: 1,
      },
      {
        globalId: childWbsId,
        projectId,
        code: "1.1",
        title: "Synthetic design review",
        parentId: rootWbsId,
        ownerRoleAssignmentId: qualityRoleId,
        plannedStart: "2026-07-25",
        plannedFinish: "2026-07-31",
        milestone: true,
        statusKey: "not_started",
        statusLabelSource: "Not started",
        progressPercent: 0,
        critical: false,
        version: 1,
      },
    ],
    dependencies: [
      {
        globalId: "71000000-0000-4000-8000-000000000001",
        projectId,
        predecessorItemId: childWbsId,
        successorItemId: rootWbsId,
        version: 1,
      },
    ],
    baselines: [
      {
        globalId: baselineId,
        projectId,
        projectVersion: 3,
        workPolicyRef: projectWorkPolicyFixture,
        label: "Synthetic approved plan",
        snapshotHash:
          "2222222222222222222222222222222222222222222222222222222222222222",
        capturedAt: "2026-07-23T10:00:00Z",
        capturedBy: "project.owner@example.invalid",
        version: 1,
      },
    ],
    baselineComparison: {
      baselineId,
      baselineProjectVersion: 3,
      currentProjectVersion: projectWorkProjectVersion,
      items: [
        {
          wbsItemId: rootWbsId,
          baselinePlannedStart: "2026-07-24",
          baselinePlannedFinish: "2026-08-08",
          currentPlannedStart: "2026-07-25",
          currentPlannedFinish: "2026-08-10",
          startVarianceDays: 1,
          finishVarianceDays: 2,
          critical: true,
        },
        {
          wbsItemId: childWbsId,
          baselinePlannedStart: "2026-07-25",
          baselinePlannedFinish: "2026-07-31",
          currentPlannedStart: "2026-07-25",
          currentPlannedFinish: "2026-07-31",
          startVarianceDays: 0,
          finishVarianceDays: 0,
          critical: false,
        },
      ],
    },
    permissions: {
      canView: true,
      canContribute: true,
      canAdminister: false,
    },
  };
}

export function projectDomainWorkItemsFixture(): DomainWorkItemPageViewModel {
  const cockpit = projectWorkCockpitFixture();
  const projectId = cockpit.project.globalId;
  const stageId = "44444444-4444-4444-8444-444444444444";
  const wbsItemId = "70000000-0000-4000-8000-000000000002";
  const source = {
    sourceSystem: "NPI_ONE",
    editableIn: "NPI_ONE",
    syncState: "local",
  } as const;
  return {
    projectId,
    projectVersion: projectWorkProjectVersion,
    items: [
      {
        globalId: "80000000-0000-4000-8000-000000000001",
        projectId,
        kind: "risk",
        title: "Synthetic resin availability risk",
        detail: "Synthetic supplier lead time may exceed the plan.",
        context: {
          projectId,
          stageId,
        },
        ownerUserId: "engineering.lead@example.invalid",
        dueAt: "2026-07-24T12:00:00Z",
        severity: "high",
        blocking: false,
        relatedWorkItemIds: [],
        workPolicyRef: projectWorkPolicyFixture,
        stateKey: "identified",
        stateLabelSource: "Identified",
        overdue: true,
        version: 1,
        createdAt: "2026-07-23T10:10:00Z",
        lastChangedAt: "2026-07-23T10:10:00Z",
        source,
      },
      {
        globalId: "80000000-0000-4000-8000-000000000002",
        projectId,
        kind: "issue",
        title: "Synthetic interface dimension issue",
        context: {
          projectId,
          stageId,
          wbsItemId,
        },
        ownerUserId: "quality.lead@example.invalid",
        dueAt: "2026-07-25T12:00:00Z",
        severity: "critical",
        blocking: true,
        relatedWorkItemIds: ["80000000-0000-4000-8000-000000000001"],
        workPolicyRef: projectWorkPolicyFixture,
        stateKey: "open",
        stateLabelSource: "Open",
        overdue: false,
        version: 1,
        createdAt: "2026-07-23T10:20:00Z",
        lastChangedAt: "2026-07-23T10:30:00Z",
        source,
      },
      {
        globalId: "80000000-0000-4000-8000-000000000003",
        projectId,
        kind: "action",
        title: "Synthetic drawing correction",
        context: { projectId, wbsItemId },
        ownerUserId: "tooling.lead@example.invalid",
        dueAt: "2026-07-27T12:00:00Z",
        severity: "medium",
        blocking: false,
        relatedWorkItemIds: ["80000000-0000-4000-8000-000000000002"],
        workPolicyRef: projectWorkPolicyFixture,
        stateKey: "open",
        stateLabelSource: "Open",
        overdue: false,
        version: 1,
        createdAt: "2026-07-23T10:40:00Z",
        lastChangedAt: "2026-07-23T10:40:00Z",
        source,
      },
      {
        globalId: "80000000-0000-4000-8000-000000000004",
        projectId,
        kind: "decision_request",
        title: "Synthetic design variance decision",
        context: { projectId },
        ownerUserId: "project.owner@example.invalid",
        dueAt: "2026-07-28T12:00:00Z",
        severity: "low",
        blocking: false,
        relatedWorkItemIds: [],
        workPolicyRef: projectWorkPolicyFixture,
        stateKey: "requested",
        stateLabelSource: "Requested",
        overdue: false,
        version: 1,
        createdAt: "2026-07-23T10:50:00Z",
        lastChangedAt: "2026-07-23T10:50:00Z",
        source,
      },
    ],
    nextCursor: null,
  };
}
