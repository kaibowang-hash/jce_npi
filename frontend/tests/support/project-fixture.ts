import type { ProjectCockpitViewModel } from "../../src/domain/view-models";

export function projectCockpitFixture(
  overrides: Partial<ProjectCockpitViewModel["project"]> = {},
): ProjectCockpitViewModel {
  return {
    project: {
      globalId: "11111111-1111-4111-8111-111111111111",
      businessCode: "SYN-PROJECT-001",
      title: "Synthetic project cockpit",
      projectType: "new_tool",
      state: "draft",
      version: 1,
      tenantId: "synthetic-tenant",
      ownerUserId: "project.owner@example.invalid",
      targetSop: "2026-10-15",
      createdAt: "2026-07-22T09:00:00Z",
      lastChangedAt: "2026-07-22T09:10:00Z",
      lastChangedBy: "project.owner@example.invalid",
      source: {
        sourceSystem: "NPI_ONE",
        editableIn: "NPI_ONE",
        syncState: "local",
      },
      ...overrides,
    },
    templateRef: {
      globalId: "22222222-2222-4222-8222-222222222222",
      code: "SYNTHETIC-PROJECT-TEMPLATE",
      version: 1,
      snapshotHash:
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    },
    references: [
      {
        type: "customer",
        sourceSystem: "NPI_ONE",
        sourceObjectId: "SYN-CUSTOMER-001",
      },
      {
        type: "part",
        sourceSystem: "NPI_ONE",
        sourceObjectId: "SYN-PART-001",
        globalId: "33333333-3333-4333-8333-333333333333",
      },
    ],
    gates: [
      {
        globalId: "44444444-4444-4444-8444-444444444444",
        key: "G0",
        title: "Synthetic feasibility shell",
        sequence: 1,
        state: "not_started",
        version: 1,
      },
      {
        globalId: "55555555-5555-4555-8555-555555555555",
        key: "G1",
        title: "Synthetic initiation shell",
        sequence: 2,
        state: "not_started",
        version: 1,
      },
    ],
    permissions: {
      canView: true,
      canContribute: true,
      canAdminister: false,
    },
  };
}
