import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { frontendRoot, repositoryRoot } from "./shared.mjs";

const input = path.join(repositoryRoot, "design", "design-tokens.json");
const output = path.join(frontendRoot, "src", "generated", "tokens.css");
const checkOnly = process.argv.includes("--check");
const tokenDocument = JSON.parse(await readFile(input, "utf8"));
const declarations = [];

for (const [group, tokens] of Object.entries(tokenDocument)) {
  if (group.startsWith("$") || group === "meta" || group === "usageRatios")
    continue;
  if (typeof tokens !== "object" || tokens === null) continue;
  for (const [name, definition] of Object.entries(tokens)) {
    if (
      typeof definition !== "object" ||
      definition === null ||
      !("value" in definition)
    )
      continue;
    if (group === "motion" && name === "principle") continue;
    const variable = `--npi-${group}-${name.replaceAll(".", "-")}`;
    declarations.push(`  ${variable}: ${definition.value};`);
  }
}

const generated = [
  "/* Generated from design/design-tokens.json. Do not edit. */",
  ":root {",
  ...declarations,
  "}",
  "",
].join("\n");

if (checkOnly) {
  const current = await readFile(output, "utf8").catch(() => "");
  if (current !== generated)
    throw new Error("Generated CSS tokens are stale. Run npm run generate.");
} else {
  await writeFile(output, generated, "utf8");
}
