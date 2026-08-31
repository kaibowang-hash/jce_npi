import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import {
  catalogFromRows,
  extractTranslationSources,
  frontendRoot,
  parseCsv,
  repositoryRoot,
} from "./shared.mjs";

const checkOnly = process.argv.includes("--check");
const output = path.join(frontendRoot, "src", "generated", "catalogs.ts");
const locales = ["zh", "zh-TW"];
const sources = await extractTranslationSources();
const catalogs = {};
let versionInput = "";

for (const locale of locales) {
  const file = path.join(
    repositoryRoot,
    "apps",
    "npi_core",
    "npi_core",
    "translations",
    `${locale}.csv`,
  );
  const content = await readFile(file, "utf8");
  versionInput += `${locale}\0${content}\0`;
  const catalog = catalogFromRows(parseCsv(content, file), file);
  const missing = [...sources.keys()].filter((source) => !catalog.has(source));
  const unused = [...catalog.keys()].filter((source) => !sources.has(source));
  if (missing.length > 0)
    throw new Error(`${locale} is missing: ${missing.join(" | ")}`);
  if (unused.length > 0)
    throw new Error(`${locale} has unused sources: ${unused.join(" | ")}`);
  catalogs[locale] = Object.fromEntries(
    [...catalog.entries()].sort(([left], [right]) => left.localeCompare(right)),
  );
}

const version = createHash("sha256")
  .update(versionInput)
  .digest("hex")
  .slice(0, 16);
const generated = [
  "/* Generated from npi_core Frappe CSV catalogs. Do not edit. */",
  `export const catalogVersion = '${version}';`,
  `export const catalogs: Readonly<Record<"zh" | "zh-TW", Readonly<Record<string, string>>>> = ${JSON.stringify(catalogs, null, 2)};`,
  "",
].join("\n");

if (checkOnly) {
  const current = await readFile(output, "utf8").catch(() => "");
  if (current !== generated)
    throw new Error(
      "Generated React catalogs are stale. Run npm run generate.",
    );
} else {
  await writeFile(output, generated, "utf8");
}
