import type { MyWorkItemViewModel } from "../domain/view-models";

/**
 * Builds a local route only from the validated target union. The API cannot
 * supply an arbitrary browser path; the work-item query names the reachable
 * Project workspace context even before that workspace supports auto-selection.
 */
export function myWorkTargetPath(item: MyWorkItemViewModel): string {
  if (item.target.kind === "gate_review") {
    return `/projects/${encodeURIComponent(item.target.projectId)}/gates/${encodeURIComponent(item.target.gateId)}`;
  }
  const query = new URLSearchParams({
    tab: "work-items",
    workItem: item.target.workItemId,
  });
  return `/projects/${encodeURIComponent(item.project.globalId)}?${query.toString()}`;
}
