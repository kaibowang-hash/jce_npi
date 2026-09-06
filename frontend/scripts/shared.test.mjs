import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import {
  extractTranslationSources,
  extractTypeScriptTranslationCalls,
  repositoryRoot,
} from "./shared.mjs";

test("extracts every governed policy label from literal translator calls", async () => {
  const registry = JSON.parse(
    await readFile(
      path.join(
        repositoryRoot,
        "apps",
        "npi_core",
        "npi_core",
        "project_work",
        "policy_label_sources.json",
      ),
      "utf8",
    ),
  );
  const sources = await extractTranslationSources();
  for (const source of registry.labelSources) {
    assert.ok(sources.has(source), `${source} was not extracted`);
  }
});

test("continues to reject ordinary dynamic t calls", () => {
  assert.throws(
    () =>
      extractTypeScriptTranslationCalls(
        "export const invalid = (t, source) => t(source);",
        "ordinary-dynamic-translation.ts",
      ),
    /Translation calls must use an English string literal/u,
  );
});

test("rejects dynamic calls through a renamed typed translator", () => {
  assert.throws(
    () =>
      extractTypeScriptTranslationCalls(
        [
          "type Translator = (source: string) => string;",
          "export const invalid = (translateSource: Translator, source: string) =>",
          "  translateSource(source);",
        ].join("\n"),
        "renamed-dynamic-translation.ts",
      ),
    /Translation calls must use an English string literal/u,
  );
});

test("extracts literal calls through renamed translator aliases", () => {
  assert.deepEqual(
    extractTypeScriptTranslationCalls(
      [
        "type Translator = (source: string) => string;",
        "export const valid = (translateSource: Translator) =>",
        '  translateSource("Literal alias source");',
      ].join("\n"),
      "renamed-literal-translation.ts",
    ),
    [{ context: undefined, source: "Literal alias source" }],
  );
});

test("rejects dynamic calls through useI18n destructuring aliases", () => {
  assert.throws(
    () =>
      extractTypeScriptTranslationCalls(
        [
          "export const invalid = (source: string) => {",
          "  const { t: translateSource } = useI18n();",
          "  return translateSource(source);",
          "};",
        ].join("\n"),
        "use-i18n-alias-translation.ts",
      ),
    /Translation calls must use an English string literal/u,
  );
});

test("rejects dynamic calls through ReturnType translator aliases", () => {
  assert.throws(
    () =>
      extractTypeScriptTranslationCalls(
        [
          "export const invalid = (",
          '  translateSource: ReturnType<typeof useI18n>["t"],',
          "  source: string,",
          ") => translateSource(source);",
        ].join("\n"),
        "return-type-alias-translation.ts",
      ),
    /Translation calls must use an English string literal/u,
  );
});

test("does not treat unrelated callbacks as translators", () => {
  assert.deepEqual(
    extractTypeScriptTranslationCalls(
      [
        "export const valid = (",
        "  callback: (value: string) => string,",
        "  value: string,",
        ") => callback(value);",
      ].join("\n"),
      "unrelated-callback.ts",
    ),
    [],
  );
});
