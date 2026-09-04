import type { WorkItemViewModel } from "../domain/view-models";

export type SavedWorklistView =
  | "focus"
  | "overdue"
  | "approvals"
  | "integration";
export type WorklistGroup = "none" | "context" | "kind";

export interface WorklistQuery {
  asOf: string;
  filter: string;
  groupBy: WorklistGroup;
  limit: number;
  offset: number;
  savedView: SavedWorklistView;
  sortDescending: boolean;
}

export interface WorklistPage {
  items: readonly WorkItemViewModel[];
  limit: number;
  offset: number;
  total: number;
}

export interface WorklistDataSource {
  query(query: WorklistQuery): Promise<WorklistPage>;
}

export class PrototypeWorklistTransport implements WorklistDataSource {
  constructor(private readonly fixtures: readonly WorkItemViewModel[]) {}

  async query(query: WorklistQuery): Promise<WorklistPage> {
    await Promise.resolve();
    const normalized = query.filter.trim().toLowerCase();
    const viewItems = this.fixtures.filter((item) => {
      if (query.savedView === "overdue") return item.dueAt < query.asOf;
      if (query.savedView === "approvals")
        return item.kind === "approval" || item.kind === "decision";
      if (query.savedView === "integration") return item.kind === "integration";
      return true;
    });
    const filtered = normalized
      ? viewItems.filter((item) =>
          `${item.contextCode} ${item.contextName}`
            .toLowerCase()
            .includes(normalized),
        )
      : [...viewItems];
    filtered.sort((left, right) => {
      const groupOrder =
        query.groupBy === "context"
          ? left.contextCode.localeCompare(right.contextCode)
          : query.groupBy === "kind"
            ? left.kind.localeCompare(right.kind)
            : 0;
      if (groupOrder !== 0) return groupOrder;
      return (
        left.dueAt.localeCompare(right.dueAt) * (query.sortDescending ? -1 : 1)
      );
    });
    return {
      items: filtered.slice(query.offset, query.offset + query.limit),
      limit: query.limit,
      offset: query.offset,
      total: filtered.length,
    };
  }
}
