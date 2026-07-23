import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

export const frontendRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
export const repositoryRoot = path.resolve(frontendRoot, "..");

export async function collectFiles(root, extensions, ignored = new Set()) {
  const files = [];
  async function visit(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      if (ignored.has(entry.name)) continue;
      const resolved = path.join(directory, entry.name);
      if (entry.isDirectory()) await visit(resolved);
      else if (extensions.some((extension) => entry.name.endsWith(extension)))
        files.push(resolved);
    }
  }
  await visit(root);
  return files.sort();
}

export function extractTypeScriptTranslationCalls(content, file) {
  const sourceFile = ts.createSourceFile(
    file,
    content,
    ts.ScriptTarget.Latest,
    true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const translatorTypeNames = new Set(["Translator"]);
  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement)) continue;
    const bindings = statement.importClause?.namedBindings;
    if (!bindings || !ts.isNamedImports(bindings)) continue;
    for (const element of bindings.elements) {
      const importedName = element.propertyName?.text ?? element.name.text;
      if (importedName === "Translator")
        translatorTypeNames.add(element.name.text);
    }
  }

  const isUseI18nTypeQuery = (node) =>
    Boolean(
      node &&
      ts.isTypeQueryNode(node) &&
      ts.isIdentifier(node.exprName) &&
      node.exprName.text === "useI18n",
    );
  const isUseI18nReturnType = (node) =>
    Boolean(
      node &&
      ts.isTypeReferenceNode(node) &&
      ts.isIdentifier(node.typeName) &&
      node.typeName.text === "ReturnType" &&
      node.typeArguments?.length === 1 &&
      isUseI18nTypeQuery(node.typeArguments[0]),
    );
  const isTranslatorType = (node) =>
    Boolean(
      node &&
      ((ts.isTypeReferenceNode(node) &&
        ts.isIdentifier(node.typeName) &&
        translatorTypeNames.has(node.typeName.text)) ||
        (ts.isIndexedAccessTypeNode(node) &&
          isUseI18nReturnType(node.objectType) &&
          ts.isLiteralTypeNode(node.indexType) &&
          ts.isStringLiteral(node.indexType.literal) &&
          node.indexType.literal.text === "t")),
    );
  const isUseI18nCall = (node) =>
    Boolean(
      node &&
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "useI18n",
    );
  const translatorIdentifiers = new Set(["t"]);
  const i18nObjectIdentifiers = new Set();
  const collectTranslatorIdentifiers = (node) => {
    if (
      (ts.isParameter(node) || ts.isVariableDeclaration(node)) &&
      ts.isIdentifier(node.name) &&
      isTranslatorType(node.type)
    ) {
      translatorIdentifiers.add(node.name.text);
    }
    if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      isUseI18nCall(node.initializer)
    ) {
      i18nObjectIdentifiers.add(node.name.text);
    }
    if (
      ts.isBindingElement(node) &&
      node.propertyName &&
      ts.isIdentifier(node.propertyName) &&
      node.propertyName.text === "t" &&
      ts.isIdentifier(node.name) &&
      ts.isObjectBindingPattern(node.parent) &&
      ts.isVariableDeclaration(node.parent.parent) &&
      isUseI18nCall(node.parent.parent.initializer)
    ) {
      translatorIdentifiers.add(node.name.text);
    }
    ts.forEachChild(node, collectTranslatorIdentifiers);
  };
  collectTranslatorIdentifiers(sourceFile);

  let changed = true;
  while (changed) {
    changed = false;
    const collectTranslatorAliases = (node) => {
      if (
        ts.isVariableDeclaration(node) &&
        ts.isIdentifier(node.name) &&
        node.initializer &&
        !translatorIdentifiers.has(node.name.text) &&
        ((ts.isIdentifier(node.initializer) &&
          translatorIdentifiers.has(node.initializer.text)) ||
          (ts.isPropertyAccessExpression(node.initializer) &&
            node.initializer.name.text === "t" &&
            (isUseI18nCall(node.initializer.expression) ||
              (ts.isIdentifier(node.initializer.expression) &&
                i18nObjectIdentifiers.has(node.initializer.expression.text)))))
      ) {
        translatorIdentifiers.add(node.name.text);
        changed = true;
      }
      ts.forEachChild(node, collectTranslatorAliases);
    };
    collectTranslatorAliases(sourceFile);
  }

  const isTranslationCallee = (node) =>
    (ts.isIdentifier(node) && translatorIdentifiers.has(node.text)) ||
    (ts.isPropertyAccessExpression(node) &&
      node.name.text === "t" &&
      (isUseI18nCall(node.expression) ||
        (ts.isIdentifier(node.expression) &&
          i18nObjectIdentifiers.has(node.expression.text))));
  const calls = [];
  const visit = (node) => {
    if (ts.isCallExpression(node) && isTranslationCallee(node.expression)) {
      const [sourceNode, , contextNode] = node.arguments;
      if (!sourceNode || !ts.isStringLiteralLike(sourceNode)) {
        throw new Error(
          `Translation calls must use an English string literal: ${path.relative(repositoryRoot, file)}`,
        );
      }
      if (node.arguments.length > 3) {
        throw new Error(
          `Translation calls accept at most source, values, and context: ${path.relative(repositoryRoot, file)}`,
        );
      }
      if (contextNode && !ts.isStringLiteralLike(contextNode)) {
        throw new Error(
          `Translation contexts must use a string literal: ${path.relative(repositoryRoot, file)}`,
        );
      }
      calls.push({
        context: contextNode?.text,
        source: sourceNode.text,
      });
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return calls;
}

export async function extractTranslationSources() {
  const sourceRoot = path.join(frontendRoot, "src");
  const files = await collectFiles(
    sourceRoot,
    [".ts", ".tsx"],
    new Set(["generated"]),
  );
  const sources = new Map();

  const addSource = (source, file, kind, context) => {
    const containsInvalidCharacter = [...source].some((character) => {
      const codePoint = character.codePointAt(0) ?? 0;
      return (
        codePoint < 32 ||
        codePoint === 127 ||
        (codePoint >= 13_312 && codePoint <= 40_959) ||
        (codePoint >= 63_744 && codePoint <= 64_255)
      );
    });
    if (
      containsInvalidCharacter ||
      !/[A-Za-z]/.test(source) ||
      /(?<!\{)\{[0-9]+\}(?!\})/u.test(source)
    ) {
      throw new Error(
        `${kind} translation source must be an English literal with named placeholders: ${source}`,
      );
    }
    if (context !== undefined && !context.trim()) {
      throw new Error(
        `${kind} translation context must be a non-empty literal: ${path.relative(repositoryRoot, file)}`,
      );
    }
    const key = context ? `${source}:${context}` : source;
    const locations = sources.get(key) ?? [];
    locations.push(path.relative(repositoryRoot, file));
    sources.set(key, locations);
  };

  for (const file of files) {
    const content = await readFile(file, "utf8");
    for (const call of extractTypeScriptTranslationCalls(content, file)) {
      addSource(call.source, file, "React", call.context);
    }
  }

  const pythonRoot = path.join(repositoryRoot, "apps", "npi_core", "npi_core");
  const pythonFiles = await collectFiles(
    pythonRoot,
    [".py"],
    new Set(["__pycache__"]),
  );
  const pythonCallPattern = /\b_\(\s*(['"])((?:\\.|(?!\1).)*)\1/g;
  const pythonNonLiteralPattern = /\b_\((?!\s*['"])/g;
  for (const file of pythonFiles) {
    const content = await readFile(file, "utf8");
    if (pythonNonLiteralPattern.test(content)) {
      throw new Error(
        `Frappe translation calls must use an English string literal: ${path.relative(repositoryRoot, file)}`,
      );
    }
    for (const match of content.matchAll(pythonCallPattern)) {
      const source = match[2].replace(/\\(['"\\])/g, "$1");
      addSource(source, file, "Frappe");
    }
  }

  const integrationRoot = path.join(
    repositoryRoot,
    "apps",
    "npi_integration",
    "npi_integration",
  );
  const integrationPythonFiles = await collectFiles(
    integrationRoot,
    [".py"],
    new Set(["__pycache__"]),
  );
  for (const file of integrationPythonFiles) {
    const content = await readFile(file, "utf8");
    if (pythonNonLiteralPattern.test(content)) {
      throw new Error(
        `Frappe translation calls must use an English string literal: ${path.relative(repositoryRoot, file)}`,
      );
    }
    for (const match of content.matchAll(pythonCallPattern)) {
      addSource(match[2].replace(/\\(['"\\])/g, "$1"), file, "Frappe");
    }
  }

  for (const applicationRoot of [pythonRoot, integrationRoot]) {
    const metadataFiles = await collectFiles(
      applicationRoot,
      [".json"],
      new Set(["__pycache__"]),
    );
    for (const file of metadataFiles) {
      const metadata = JSON.parse(await readFile(file, "utf8"));
      if (metadata.doctype !== "DocType") continue;

      for (const source of [
        metadata.name,
        metadata.module,
        metadata.description,
      ]) {
        if (typeof source === "string" && source.trim())
          addSource(source.trim(), file, "DocType");
      }
      for (const field of Array.isArray(metadata.fields)
        ? metadata.fields
        : []) {
        for (const source of [field.label, field.description]) {
          if (typeof source === "string" && source.trim())
            addSource(source.trim(), file, "DocType");
        }
        if (field.fieldtype === "Select" && typeof field.options === "string") {
          for (const option of field.options
            .split("\n")
            .map((value) => value.trim())
            .filter(Boolean)) {
            addSource(option, file, "DocType select option");
          }
        }
      }
    }
  }
  return sources;
}

export function parseCsv(content, sourceName) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;

  for (let index = 0; index <= content.length; index += 1) {
    const character = content[index] ?? "\n";
    if (quoted) {
      if (character === '"' && content[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else if (character === '"') quoted = false;
      else cell += character;
      continue;
    }
    if (character === '"') quoted = true;
    else if (character === ",") {
      row.push(cell);
      cell = "";
    } else if (character === "\n") {
      row.push(cell.replace(/\r$/, ""));
      cell = "";
      if (row.some((value) => value.length > 0)) rows.push(row);
      row = [];
    } else cell += character;
  }
  if (quoted) throw new Error(`Unterminated CSV quote in ${sourceName}`);
  return rows;
}

export function catalogFromRows(rows, sourceName) {
  const catalog = new Map();
  for (const row of rows) {
    if (row.length < 2 || row.length > 3 || !row[0] || !row[1]) {
      throw new Error(
        `Invalid Frappe translation row in ${sourceName}: ${JSON.stringify(row)}`,
      );
    }
    const key = row[2] ? `${row[0]}:${row[2]}` : row[0];
    if (catalog.has(key))
      throw new Error(`Duplicate translation key ${key} in ${sourceName}`);
    catalog.set(key, row[1]);
  }
  return catalog;
}
