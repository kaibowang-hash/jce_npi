import { readFile } from "node:fs/promises";
import path from "node:path";
import ts from "typescript";
import {
  catalogFromRows,
  collectFiles,
  extractTranslationSources,
  frontendRoot,
  parseCsv,
  repositoryRoot,
} from "./shared.mjs";

const sources = await extractTranslationSources();
const problems = [];
const terminologyText = await readFile(
  path.join(repositoryRoot, "contracts", "terminology-allowlist.yaml"),
  "utf8",
);
const sourceFiles = await collectFiles(
  path.join(frontendRoot, "src"),
  [".ts", ".tsx"],
  new Set(["generated"]),
);
const visibleAttributes = new Set([
  "aria-label",
  "title",
  "placeholder",
  "alt",
]);

function hasLanguageExemption(openingElement) {
  return openingElement.attributes.properties.some(
    (attribute) =>
      ts.isJsxAttribute(attribute) &&
      attribute.name.text === "data-language-exempt",
  );
}

function isLanguageExempt(node) {
  let current = node.parent;
  while (current) {
    if (
      ts.isJsxElement(current) &&
      hasLanguageExemption(current.openingElement)
    )
      return true;
    if (ts.isJsxSelfClosingElement(current) && hasLanguageExemption(current))
      return true;
    current = current.parent;
  }
  return false;
}

function sectionLines(name) {
  const lines = terminologyText.split(/\r?\n/);
  const start = lines.findIndex((line) => line === `${name}:`);
  if (start < 0) throw new Error(`Missing terminology section: ${name}`);
  const result = [];
  for (const line of lines.slice(start + 1)) {
    if (line && !line.startsWith(" ")) break;
    result.push(line);
  }
  return result;
}

function terminologyRecords(name) {
  const records = [];
  let current = null;
  for (const line of sectionLines(name)) {
    const source = line.match(/^ {2}- source: (.+)$/)?.[1];
    if (source) {
      current = { source };
      records.push(current);
      continue;
    }
    const property = line.match(/^ {4}(zh_cn|zh_tw): (.+)$/);
    if (current && property) current[property[1]] = property[2];
  }
  return records;
}

function terminologyList(name) {
  return sectionLines(name)
    .map((line) => line.match(/^ {2}- (.+)$/)?.[1])
    .filter(Boolean);
}

function unquoteYamlScalar(value) {
  const match = /^(['"])(.*)\1$/u.exec(value);
  return match ? match[2] : value;
}

function placeholders(value) {
  return [
    ...value.matchAll(/\{\{([A-Za-z][A-Za-z0-9_]*)\}\}/g),
    ...value.matchAll(/(?<!\{)\{([A-Za-z][A-Za-z0-9_]*)\}(?!\})/g),
  ]
    .map((match) => match[1])
    .sort();
}

function containsTerm(value, term) {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^A-Za-z0-9])${escaped}(?=$|[^A-Za-z0-9])`, "u").test(
    value,
  );
}

function removeAllowedTerm(value, term) {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return value.replace(
    new RegExp(`(^|[^A-Za-z0-9])${escaped}(?=$|[^A-Za-z0-9])`, "gu"),
    "$1",
  );
}

function isInlineIdentifier(token) {
  return (
    /^[A-Z]$/u.test(token) ||
    /^[A-Z][0-9]{1,4}$/u.test(token) ||
    /^[A-Z]{2,8}-[A-Z0-9-]*[0-9][A-Z0-9-]*$/u.test(token) ||
    /^v[0-9]+$/u.test(token)
  );
}

const retainTerms = terminologyRecords("retain_terms");
const translatedTerms = terminologyRecords("translated_ui_terms");
const forbiddenEnglish = terminologyList("forbidden_general_english_in_zh_ui");
const unitTokens = new Set(
  terminologyList("unit_examples").map(unquoteYamlScalar),
);

for (const file of sourceFiles) {
  const content = await readFile(file, "utf8");
  const relative = path.relative(repositoryRoot, file);
  if (/[\u3400-\u9fff\uf900-\ufaff]/u.test(content))
    problems.push(`${relative}: Chinese UI source text is forbidden`);
  if (!file.endsWith(".tsx")) continue;
  const sourceFile = ts.createSourceFile(
    file,
    content,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const visit = (node) => {
    if (
      ts.isJsxText(node) &&
      /[A-Za-z]/.test(node.text) &&
      !isLanguageExempt(node)
    ) {
      const { line } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );
      problems.push(`${relative}:${line + 1}: hard-coded JSX text node`);
    }
    if (
      ts.isJsxAttribute(node) &&
      visibleAttributes.has(node.name.text) &&
      node.initializer &&
      ts.isStringLiteral(node.initializer) &&
      /[A-Za-z]/.test(node.initializer.text) &&
      !isLanguageExempt(node)
    ) {
      const { line } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );
      problems.push(`${relative}:${line + 1}: hard-coded visible attribute`);
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
}

let expectedKeys;
for (const locale of ["zh", "zh-TW"]) {
  const file = path.join(
    repositoryRoot,
    "apps",
    "npi_core",
    "npi_core",
    "translations",
    `${locale}.csv`,
  );
  const catalog = catalogFromRows(
    parseCsv(await readFile(file, "utf8"), file),
    file,
  );
  const localeProperty = locale === "zh" ? "zh_cn" : "zh_tw";
  for (const [source, translation] of catalog) {
    if (
      JSON.stringify(placeholders(source)) !==
      JSON.stringify(placeholders(translation))
    ) {
      problems.push(`${locale}: placeholder mismatch for ${source}`);
    }
    for (const term of retainTerms) {
      if (
        containsTerm(source, term.source) &&
        !containsTerm(translation, term[localeProperty])
      ) {
        problems.push(
          `${locale}: retained term ${term.source} drifted in ${source}`,
        );
      }
    }
    for (const word of forbiddenEnglish) {
      if (containsTerm(translation, word))
        problems.push(
          `${locale}: forbidden English ${word} remains in ${source}`,
        );
    }
    let languagePurityCandidate = translation.replace(
      /\{\{[A-Za-z][A-Za-z0-9_]*\}\}/gu,
      "",
    );
    languagePurityCandidate = languagePurityCandidate.replace(
      /(?<!\{)\{[A-Za-z][A-Za-z0-9_]*\}(?!\})/gu,
      "",
    );
    for (const term of [...retainTerms].sort(
      (left, right) =>
        right[localeProperty].length - left[localeProperty].length,
    )) {
      languagePurityCandidate = removeAllowedTerm(
        languagePurityCandidate,
        term[localeProperty],
      );
    }
    const unexpectedLatinTokens = [
      ...languagePurityCandidate.matchAll(/[A-Za-z][A-Za-z0-9._/-]*/gu),
    ]
      .map((match) => match[0])
      .filter((token) => !unitTokens.has(token) && !isInlineIdentifier(token));
    if (unexpectedLatinTokens.length > 0) {
      problems.push(
        `${locale}: unapproved Latin token ${unexpectedLatinTokens.join(", ")} remains in ${source}`,
      );
    }
  }
  for (const term of translatedTerms) {
    if (
      catalog.has(term.source) &&
      catalog.get(term.source) !== term[localeProperty]
    ) {
      problems.push(`${locale}: controlled term ${term.source} drifted`);
    }
  }
  const keys = new Set(catalog.keys());
  expectedKeys ??= keys;
  const missing = [...sources.keys()].filter((source) => !keys.has(source));
  const unused = [...keys].filter((source) => !sources.has(source));
  if (missing.length > 0)
    problems.push(`${locale}: missing ${missing.join(" | ")}`);
  if (unused.length > 0)
    problems.push(`${locale}: unused ${unused.join(" | ")}`);
  if (
    expectedKeys.size !== keys.size ||
    [...expectedKeys].some((source) => !keys.has(source))
  ) {
    problems.push(
      `${locale}: catalog source set differs from the paired locale`,
    );
  }
}
if (problems.length > 0) throw new Error(problems.join("\n"));
console.log(
  `i18n audit passed (${sources.size} literal English sources, 100% zh/zh-TW coverage)`,
);
