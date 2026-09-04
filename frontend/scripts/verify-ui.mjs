import { readFile } from "node:fs/promises";
import path from "node:path";
import { collectFiles, frontendRoot, repositoryRoot } from "./shared.mjs";

const files = await collectFiles(
  path.join(frontendRoot, "src"),
  [".css"],
  new Set(["generated"]),
);
const prohibited = [
  [/#[0-9a-f]{3,8}\b/gi, "hard-coded color"],
  [/\b(?:rgb|hsl)a?\s*\(/gi, "hard-coded color function"],
  [/\b(?:linear|radial|conic)-gradient\s*\(/gi, "gradient"],
  [/backdrop-filter\s*:/gi, "glass effect"],
  [
    /border-radius\s*:\s*(?:[3-9]|[1-9][0-9]+)px/gi,
    "ordinary radius above 2px",
  ],
  [
    /box-shadow\s*:\s*(?!var\(--npi-shadow-overlay\)|var\(--npi-shadow-none\)|none)/gi,
    "unapproved shadow",
  ],
  [
    /\bborder(?:-(?:top|right|bottom|left))?(?:-width)?\s*:\s*(?:\d*\.?\d+px|0\b|none\b)/gi,
    "non-token border width",
  ],
];
const problems = [];
for (const file of files) {
  const content = await readFile(file, "utf8");
  for (const [pattern, label] of prohibited) {
    if (pattern.test(content))
      problems.push(`${path.relative(repositoryRoot, file)}: ${label}`);
  }
}
const tokens = JSON.parse(
  await readFile(
    path.join(repositoryRoot, "design", "design-tokens.json"),
    "utf8",
  ),
);
if (
  tokens.radius.subtle.value !== "2px" ||
  tokens.shadow.none.value !== "none"
) {
  problems.push("design token radius/shadow baseline drifted");
}
if (
  tokens.color["brand.primary"].value !== tokens.color["action.primary"].value
) {
  problems.push("brand and action primary colors must remain a single primary");
}
if (problems.length > 0) throw new Error(problems.join("\n"));
console.log(`industrial UI static audit passed (${files.length} style files)`);
