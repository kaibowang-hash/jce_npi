import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { frontendRoot, repositoryRoot } from "./shared.mjs";

const input = path.join(
  repositoryRoot,
  "apps",
  "npi_core",
  "npi_core",
  "project_work",
  "policy_label_sources.json",
);
const output = path.join(
  frontendRoot,
  "src",
  "generated",
  "project-policy-label-sources.ts",
);
const checkOnly = process.argv.includes("--check");

function isRecord(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function parseRegistry(value) {
  if (
    !isRecord(value) ||
    Object.keys(value).length !== 2 ||
    value.schemaVersion !== 1 ||
    !Array.isArray(value.labelSources)
  ) {
    throw new Error(
      "Policy label registry must contain only schemaVersion 1 and labelSources.",
    );
  }

  const labelSources = value.labelSources;
  if (
    labelSources.length === 0 ||
    labelSources.some(
      (source) =>
        typeof source !== "string" ||
        source.length < 1 ||
        source.length > 140 ||
        !/[A-Za-z]/u.test(source) ||
        !/^[\x20-\x7E]+$/u.test(source) ||
        source.trim() !== source,
    )
  ) {
    throw new Error(
      "Policy label sources must be non-empty, bounded English strings without surrounding whitespace.",
    );
  }
  if (new Set(labelSources).size !== labelSources.length) {
    throw new Error("Policy label sources must be unique.");
  }
  const sorted = [...labelSources].sort((left, right) =>
    left < right ? -1 : left > right ? 1 : 0,
  );
  if (labelSources.some((source, index) => source !== sorted[index])) {
    throw new Error("Policy label sources must use deterministic sort order.");
  }
  return labelSources;
}

const registry = parseRegistry(JSON.parse(await readFile(input, "utf8")));
const generated = [
  "/* Generated from apps/npi_core/npi_core/project_work/policy_label_sources.json. Do not edit. */",
  "export const projectPolicyLabelSources = [",
  ...registry.map((source) => `  ${JSON.stringify(source)},`),
  "] as const;",
  "",
  "export type ProjectPolicyLabelSource =",
  "  (typeof projectPolicyLabelSources)[number];",
  "",
  "const projectPolicyLabelSourceSet: ReadonlySet<string> = new Set(",
  "  projectPolicyLabelSources,",
  ");",
  "",
  "export function isProjectPolicyLabelSource(",
  "  value: unknown,",
  "): value is ProjectPolicyLabelSource {",
  '  return typeof value === "string" && projectPolicyLabelSourceSet.has(value);',
  "}",
  "",
].join("\n");

if (checkOnly) {
  const current = await readFile(output, "utf8").catch(() => "");
  if (current !== generated) {
    throw new Error(
      "Generated Project policy label sources are stale. Run npm run generate.",
    );
  }
} else {
  await writeFile(output, generated, "utf8");
}
