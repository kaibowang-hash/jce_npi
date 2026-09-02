import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { measureBuild, verifyBudgets } from "./verify-build-budget.mjs";

const tinyBudgets = {
  initialCss: { gzip: 100, raw: 100 },
  initialJavaScript: { gzip: 100, raw: 100 },
  lazyJavaScript: { gzip: 100, raw: 100 },
  localeCatalogJavaScript: { gzip: 100, raw: 100 },
};

test("measures entry assets separately from lazy chunks", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "npi-build-budget-"));
  try {
    await mkdir(path.join(directory, "assets"));
    await writeFile(
      path.join(directory, "index.html"),
      '<script type="module" src="/assets/index-a.js"></script>' +
        '<link rel="stylesheet" href="/assets/index-a.css">',
    );
    await writeFile(path.join(directory, "assets", "index-a.js"), "entry();");
    await writeFile(path.join(directory, "assets", "index-a.css"), "body{}");
    await writeFile(path.join(directory, "assets", "route-b.js"), "route();");
    await writeFile(
      path.join(directory, "assets", "catalog-zh-c.js"),
      "catalog();",
    );

    const measurements = await measureBuild(directory);
    assert.deepEqual(
      measurements.initialJavaScript.map((asset) => asset.file),
      ["index-a.js"],
    );
    assert.deepEqual(
      measurements.lazyJavaScript.map((asset) => asset.file),
      ["route-b.js"],
    );
    assert.deepEqual(
      measurements.localeCatalogJavaScript.map((asset) => asset.file),
      ["catalog-zh-c.js"],
    );
    assert.equal(
      verifyBudgets(measurements, tinyBudgets).largestLazyJavaScript.file,
      "route-b.js",
    );
  } finally {
    await rm(directory, { force: true, recursive: true });
  }
});

test("fails closed when an entry, route, or locale asset exceeds its budget", () => {
  assert.throws(
    () =>
      verifyBudgets(
        {
          initialCss: [{ file: "index.css", gzip: 1, raw: 1 }],
          initialJavaScript: [{ file: "index.js", gzip: 5, raw: 11 }],
          lazyJavaScript: [],
          localeCatalogJavaScript: [],
        },
        {
          initialCss: { gzip: 10, raw: 10 },
          initialJavaScript: { gzip: 10, raw: 10 },
          lazyJavaScript: { gzip: 10, raw: 10 },
          localeCatalogJavaScript: { gzip: 10, raw: 10 },
        },
      ),
    /Initial JavaScript exceeds its budget/u,
  );
  assert.throws(
    () =>
      verifyBudgets(
        {
          initialCss: [{ file: "index.css", gzip: 1, raw: 1 }],
          initialJavaScript: [{ file: "index.js", gzip: 1, raw: 1 }],
          lazyJavaScript: [{ file: "route.js", gzip: 5, raw: 11 }],
          localeCatalogJavaScript: [],
        },
        {
          initialCss: { gzip: 10, raw: 10 },
          initialJavaScript: { gzip: 10, raw: 10 },
          lazyJavaScript: { gzip: 10, raw: 10 },
          localeCatalogJavaScript: { gzip: 10, raw: 10 },
        },
      ),
    /Lazy JavaScript route.js exceeds its budget/u,
  );
  assert.throws(
    () =>
      verifyBudgets(
        {
          initialCss: [{ file: "index.css", gzip: 1, raw: 1 }],
          initialJavaScript: [{ file: "index.js", gzip: 1, raw: 1 }],
          lazyJavaScript: [],
          localeCatalogJavaScript: [
            { file: "catalog-zh.js", gzip: 5, raw: 11 },
          ],
        },
        {
          initialCss: { gzip: 10, raw: 10 },
          initialJavaScript: { gzip: 10, raw: 10 },
          lazyJavaScript: { gzip: 10, raw: 10 },
          localeCatalogJavaScript: { gzip: 10, raw: 10 },
        },
      ),
    /Locale catalog JavaScript catalog-zh.js exceeds its budget/u,
  );
});
