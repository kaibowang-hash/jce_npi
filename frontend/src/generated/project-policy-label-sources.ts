/* Generated from apps/npi_core/npi_core/project_work/policy_label_sources.json. Do not edit. */
export const projectPolicyLabelSources = [
  "Cancelled",
  "Closed",
  "Completed",
  "Draft",
  "Identified",
  "In progress",
  "Not started",
  "Open",
  "Requested",
] as const;

export type ProjectPolicyLabelSource =
  (typeof projectPolicyLabelSources)[number];

const projectPolicyLabelSourceSet: ReadonlySet<string> = new Set(
  projectPolicyLabelSources,
);

export function isProjectPolicyLabelSource(
  value: unknown,
): value is ProjectPolicyLabelSource {
  return typeof value === "string" && projectPolicyLabelSourceSet.has(value);
}
