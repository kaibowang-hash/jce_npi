import { readFile, writeFile } from "node:fs/promises";

const evidenceScope = process.env.NPI_EVIDENCE_SCOPE?.trim() || "phase-4";
if (
  !/^[a-z0-9]+(?:-[a-z0-9]+)*(?:\/[a-z0-9]+(?:-[a-z0-9]+)*)*$/u.test(
    evidenceScope,
  )
) {
  throw new Error("NPI_EVIDENCE_SCOPE contains an unsafe path segment.");
}
const summaryUrl = new URL(
  `../../implementation/evidence/${evidenceScope}/coverage/coverage-summary.json`,
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
