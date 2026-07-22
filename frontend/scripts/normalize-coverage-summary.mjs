import { readFile, writeFile } from "node:fs/promises";

const summaryUrl = new URL(
  "../../implementation/evidence/phase-3/coverage/coverage-summary.json",
  import.meta.url,
);
const rawSummary = JSON.parse(await readFile(summaryUrl, "utf8"));

if (!rawSummary.total || typeof rawSummary.total !== "object") {
  throw new Error("Coverage summary does not contain aggregate totals.");
}

const portableSummary = {
  schemaVersion: 1,
  source: "vitest-v8-json-summary",
  total: rawSummary.total,
};

await writeFile(summaryUrl, `${JSON.stringify(portableSummary, null, 2)}\n`);
console.log("portable coverage summary written (aggregate totals only)");
