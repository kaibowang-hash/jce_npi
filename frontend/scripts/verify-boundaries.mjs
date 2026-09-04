import { readFile } from "node:fs/promises";
import path from "node:path";
import { collectFiles, frontendRoot, repositoryRoot } from "./shared.mjs";

const sourceRoot = path.join(frontendRoot, "src");
const files = await collectFiles(sourceRoot, [".ts", ".tsx"]);
const problems = [];
const prohibitedIconDependencyPattern =
  /^(?:@primer\/(?:octicons|react)|octicons|react-icons)$/u;
const prohibitedIconImportPattern =
  /(?:from\s+|import\s*)["'](?:@primer\/(?:octicons|react)|octicons|react-icons)(?:\/[^"']*)?["']/u;
for (const file of files) {
  const content = await readFile(file, "utf8");
  const relative = path.relative(repositoryRoot, file);
  if (
    content.includes("@siemens/") &&
    !relative.startsWith("frontend/src/ui-adapters/")
  ) {
    problems.push(`${relative}: Siemens imports must stay inside ui-adapters`);
  }
  if (prohibitedIconImportPattern.test(content)) {
    problems.push(
      `${relative}: unapproved Primer, Octicons, or direct icon-vendor imports are forbidden`,
    );
  }
  if (/\/api\/resource\b/.test(content))
    problems.push(`${relative}: raw DocType API is forbidden`);
  if (/https?:\/\/[^'"\s]*erpnext/i.test(content))
    problems.push(`${relative}: browser-to-ERP URL is forbidden`);
}
const html = await readFile(path.join(frontendRoot, "index.html"), "utf8");
if (
  !html.includes('data-ix-theme="classic"') ||
  !html.includes('data-ix-color-schema="light"')
) {
  problems.push(
    "frontend/index.html: Classic Light root attributes are required",
  );
}
const packageManifest = JSON.parse(
  await readFile(path.join(frontendRoot, "package.json"), "utf8"),
);
for (const dependencyName of Object.keys({
  ...(packageManifest.dependencies ?? {}),
  ...(packageManifest.devDependencies ?? {}),
})) {
  if (prohibitedIconDependencyPattern.test(dependencyName)) {
    problems.push(
      `frontend/package.json: unapproved icon dependency ${dependencyName} is forbidden`,
    );
  }
}
if (problems.length > 0) throw new Error(problems.join("\n"));
console.log(`boundary audit passed (${files.length} source files)`);
