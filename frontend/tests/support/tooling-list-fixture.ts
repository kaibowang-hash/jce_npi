import {
  toolingListColumnIds,
  type ToolingExportPackage,
  type ToolingListFilterSnapshot,
  type ToolingListPage,
  type ToolingListPreference,
  type ToolingListRow,
} from "../../src/api/tooling-list-data-source";
import type { ToolingCockpitViewModel } from "../../src/api/tooling-data-source";

export const toolingListIds = {
  exportPackage: "77777777-7777-4777-8777-777777777777",
  masterOne: "22222222-2222-4222-8222-222222222222",
  masterTwo: "33333333-3333-4333-8333-333333333333",
  originProject: "44444444-4444-4444-8444-444444444444",
  preference: "66666666-6666-4666-8666-666666666666",
  project: "11111111-1111-4111-8111-111111111111",
} as const;

export function toolingListFilter(
  overrides: Partial<ToolingListFilterSnapshot> = {},
): ToolingListFilterSnapshot {
  return {
    groupKey: "none",
    search: "",
    sortDirection: "asc",
    sortKey: "title",
    viewId: "all",
    ...overrides,
  };
}

export function toolingListRows(): readonly ToolingListRow[] {
  return [
    {
      applicabilityCount: 2,
      customerOwnedSet: false,
      designRevisionCount: 1,
      distinctPartRevisionCount: 2,
      latestRevisionNumber: 3,
      originatingProjectGlobalId: toolingListIds.project,
      physicalSetCount: 1,
      projectCode: "NPI-2026-001",
      projectGlobalId: toolingListIds.project,
      source: "manual",
      title: "Front housing mould",
      toolingMasterGlobalId: toolingListIds.masterOne,
      toolingMasterSnapshotHash: "a".repeat(64),
    },
    {
      applicabilityCount: 1,
      customerOwnedSet: true,
      designRevisionCount: 0,
      distinctPartRevisionCount: 1,
      latestRevisionNumber: null,
      originatingProjectGlobalId: toolingListIds.originProject,
      physicalSetCount: 2,
      projectCode: "NPI-2026-001",
      projectGlobalId: toolingListIds.project,
      source: "controlled_xlsx_import",
      title: "Connector insert mould",
      toolingMasterGlobalId: toolingListIds.masterTwo,
      toolingMasterSnapshotHash: "b".repeat(64),
    },
  ];
}

export function toolingListCockpit(): ToolingCockpitViewModel {
  const source = {
    editableIn: "NPI_ONE" as const,
    sourceSystem: "NPI_ONE" as const,
    syncState: "local" as const,
  };
  return {
    applicability: [],
    downstream: {
      erp: { reasonCode: "erp_projection_unavailable", state: "unavailable" },
      lifecycle: {
        reasonCode: "lifecycle_policy_unavailable",
        state: "unavailable",
      },
      physicalSet: {
        reasonCode: "physical_set_not_delivered",
        state: "unavailable",
      },
      revision: {
        reasonCode: "tooling_revision_not_delivered",
        state: "unavailable",
      },
      trial: { reasonCode: "trial_not_delivered", state: "unavailable" },
    },
    masters: toolingListRows().map((row) => ({
      globalId: row.toolingMasterGlobalId,
      originatingProjectGlobalId: row.originatingProjectGlobalId,
      snapshotHash: row.toolingMasterSnapshotHash,
      source,
      title: row.title,
    })),
    parts: [],
    permissions: {
      createApplicability: false,
      createMaster: false,
      createPart: false,
      createRequirement: false,
      transitionLifecycle: false,
      view: true,
    },
    project: {
      businessCode: "NPI-2026-001",
      globalId: toolingListIds.project,
      title: "Synthetic Tooling List Project",
    },
    requirements: [],
  };
}

export function toolingListPage(
  overrides: Partial<ToolingListPage> = {},
): ToolingListPage {
  return {
    filter: toolingListFilter(),
    items: toolingListRows(),
    nextCursor: null,
    pageSize: 50,
    permissions: {
      canExport: true,
      exportUnavailableReason: null,
      view: true,
    },
    projectGlobalId: toolingListIds.project,
    querySnapshotHash: "c".repeat(64),
    totalCount: 2,
    ...overrides,
  };
}

export function toolingListPreference(
  stored = true,
  filter = toolingListFilter(),
): ToolingListPreference {
  return {
    globalId: stored ? toolingListIds.preference : null,
    optimisticVersion: stored ? 1 : 0,
    preference: {
      columnOrder: toolingListColumnIds,
      columnWidths: toolingListColumnIds.map((columnId) => ({
        columnId,
        width: columnId === "tooling" ? 260 : columnId === "origin" ? 184 : 112,
      })),
      filter,
      gridId: "tooling-list",
      hiddenColumns: [],
      tableSchemaVersion: "tooling-list-grid-v1",
      viewId: filter.viewId,
    },
    snapshotHash: stored ? "d".repeat(64) : null,
    stored,
  };
}

export function toolingExportPackage(
  overrides: Partial<ToolingExportPackage> = {},
): ToolingExportPackage {
  const rows = toolingListRows();
  return {
    confidentialityClass: "internal_project",
    createdByUserId: "tooling.engineer@example.invalid",
    expiresAt: "2026-08-10T10:00:00Z",
    fileName: "tooling-object-package.zip",
    generatedAt: "2026-08-10T09:00:00Z",
    globalId: toolingListIds.exportPackage,
    language: "en",
    manifestSha256: "e".repeat(64),
    mimeType: "application/zip",
    mode: "selection",
    objectCount: rows.length,
    objectRefs: rows.map((row) => ({
      snapshotHash: row.toolingMasterSnapshotHash,
      toolingMasterGlobalId: row.toolingMasterGlobalId,
    })),
    projectGlobalId: toolingListIds.project,
    querySnapshotHash: null,
    sha256: "f".repeat(64),
    sizeBytes: 128,
    snapshotHash: "1".repeat(64),
    ...overrides,
  };
}
