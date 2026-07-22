import { readFile } from "node:fs/promises";
import path from "node:path";
import { collectFiles, frontendRoot, repositoryRoot } from "./shared.mjs";

const sourceRoot = path.join(frontendRoot, "src");
const files = await collectFiles(sourceRoot, [".ts", ".tsx"]);
const problems = [];
for (const file of files) {
  const content = await readFile(file, "utf8");
  const relative = path.relative(repositoryRoot, file);
  if (
    content.includes("@siemens/") &&
    !relative.startsWith("frontend/src/ui-adapters/")
  ) {
    problems.push(`${relative}: Siemens imports must stay inside ui-adapters`);
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
if (problems.length > 0) throw new Error(problems.join("\n"));
console.log(`boundary audit passed (${files.length} source files)`);
