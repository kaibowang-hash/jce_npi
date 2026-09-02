import { gzipSync } from "node:zlib";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);

export const budgets = Object.freeze({
  initialJavaScript: Object.freeze({ raw: 850_000, gzip: 220_000 }),
  initialCss: Object.freeze({ raw: 380_000, gzip: 42_000 }),
  lazyJavaScript: Object.freeze({ raw: 500_000, gzip: 110_000 }),
  localeCatalogJavaScript: Object.freeze({ raw: 700_000, gzip: 180_000 }),
});

function assetReferences(html, pattern) {
  return [...html.matchAll(pattern)].map((match) => path.basename(match[1]));
}

async function assetSize(directory, fileName) {
  const content = await readFile(path.join(directory, "assets", fileName));
  return {
    file: fileName,
    gzip: gzipSync(content, { level: 9, mtime: 0 }).byteLength,
    raw: content.byteLength,
  };
}

export async function measureBuild(directory) {
  const html = await readFile(path.join(directory, "index.html"), "utf8");
  const initialJavaScriptNames = assetReferences(
    html,
    /<script[^>]+src=["']([^"']+\.js)["'][^>]*>/gu,
  );
  const initialCssNames = assetReferences(
    html,
    /<link[^>]+href=["']([^"']+\.css)["'][^>]*>/gu,
  );
  if (initialJavaScriptNames.length === 0 || initialCssNames.length === 0) {
    throw new Error("The production entry assets could not be identified.");
  }
  const files = await readdir(path.join(directory, "assets"));
  const initialJavaScript = await Promise.all(
    initialJavaScriptNames.map((fileName) => assetSize(directory, fileName)),
  );
  const initialCss = await Promise.all(
    initialCssNames.map((fileName) => assetSize(directory, fileName)),
  );
  const initialSet = new Set(initialJavaScriptNames);
  const localeCatalogNames = files
    .filter(
      (fileName) =>
        fileName.startsWith("catalog-zh-") ||
        fileName.startsWith("catalog-zh-TW-"),
    )
    .sort();
  const localeCatalogSet = new Set(localeCatalogNames);
  const localeCatalogJavaScript = await Promise.all(
    localeCatalogNames.map((fileName) => assetSize(directory, fileName)),
  );
  const lazyJavaScript = await Promise.all(
    files
      .filter(
        (fileName) =>
          fileName.endsWith(".js") &&
          !initialSet.has(fileName) &&
          !localeCatalogSet.has(fileName),
      )
      .sort()
      .map((fileName) => assetSize(directory, fileName)),
  );
  return {
    initialJavaScript,
    initialCss,
    lazyJavaScript,
    localeCatalogJavaScript,
  };
}

function assertTotalWithin(label, assets, budget) {
  const total = assets.reduce(
    (value, asset) => ({
      gzip: value.gzip + asset.gzip,
      raw: value.raw + asset.raw,
    }),
    { gzip: 0, raw: 0 },
  );
  if (total.raw > budget.raw || total.gzip > budget.gzip) {
    throw new Error(
      `${label} exceeds its budget: ${total.raw}/${total.gzip} bytes raw/gzip; ` +
        `allowed ${budget.raw}/${budget.gzip}.`,
    );
  }
  return total;
}

export function verifyBudgets(measurements, configuredBudgets = budgets) {
  const initialJavaScript = assertTotalWithin(
    "Initial JavaScript",
    measurements.initialJavaScript,
    configuredBudgets.initialJavaScript,
  );
  const initialCss = assertTotalWithin(
    "Initial CSS",
    measurements.initialCss,
    configuredBudgets.initialCss,
  );
  for (const asset of measurements.lazyJavaScript) {
    if (
      asset.raw > configuredBudgets.lazyJavaScript.raw ||
      asset.gzip > configuredBudgets.lazyJavaScript.gzip
    ) {
      throw new Error(
        `Lazy JavaScript ${asset.file} exceeds its budget: ` +
          `${asset.raw}/${asset.gzip} bytes raw/gzip; allowed ` +
          `${configuredBudgets.lazyJavaScript.raw}/${configuredBudgets.lazyJavaScript.gzip}.`,
      );
    }
  }
  for (const asset of measurements.localeCatalogJavaScript) {
    if (
      asset.raw > configuredBudgets.localeCatalogJavaScript.raw ||
      asset.gzip > configuredBudgets.localeCatalogJavaScript.gzip
    ) {
      throw new Error(
        `Locale catalog JavaScript ${asset.file} exceeds its budget: ` +
          `${asset.raw}/${asset.gzip} bytes raw/gzip; allowed ` +
          `${configuredBudgets.localeCatalogJavaScript.raw}/${configuredBudgets.localeCatalogJavaScript.gzip}.`,
      );
    }
  }
  return {
    budgets: configuredBudgets,
    initialCss,
    initialJavaScript,
    largestLazyJavaScript: measurements.lazyJavaScript.reduce(
      (largest, asset) => (asset.raw > largest.raw ? asset : largest),
      { file: null, gzip: 0, raw: 0 },
    ),
    largestLocaleCatalogJavaScript: measurements.localeCatalogJavaScript.reduce(
      (largest, asset) => (asset.raw > largest.raw ? asset : largest),
      { file: null, gzip: 0, raw: 0 },
    ),
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const summary = verifyBudgets(
    await measureBuild(path.join(frontendRoot, "dist")),
  );
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
}
