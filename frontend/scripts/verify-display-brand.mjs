import { createHash } from "node:crypto";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

import {
  collectFiles,
  frontendRoot,
  parseCsv,
  repositoryRoot,
} from "./shared.mjs";
import {
  assertNoDeferredCoreAssets,
  assertOnlyApprovedStaticAssets,
} from "./deferred-core-asset-guard.mjs";

const brandDirectory = path.join(repositoryRoot, "docs", "Brand Asset");
const instructionFile = path.join(
  brandDirectory,
  "Brand Asset Instruction.csv",
);
const adapterFile = path.join(
  frontendRoot,
  "src",
  "ui-adapters",
  "display-brand.tsx",
);
const indexFile = path.join(frontendRoot, "index.html");
const viteConfigFile = path.join(frontendRoot, "vite.config.ts");
const publicDirectory = path.join(frontendRoot, "public");
const distDirectory = path.join(frontendRoot, "dist");
const exactLaunchFlowAssetNames = [
  "Company LOGO.svg",
  "LaunchFlow Icon.svg",
  "LaunchFlow-logo_Standard.svg",
  "LaunchFlow-logo_White.svg",
  "Loading.svg",
].sort();

async function collectOptionalFiles(root, extensions) {
  try {
    return await collectFiles(root, extensions);
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT")
      return [];
    throw error;
  }
}

const instructionRows = parseCsv(
  await readFile(instructionFile, "utf8"),
  instructionFile,
);
const header = instructionRows.shift();
if (
  !header ||
  header.length !== 3 ||
  header[0].replace(/^\uFEFF/u, "") !== "Document Name" ||
  header[1] !== "Usage Scope" ||
  header[2] !== "Instruction"
) {
  throw new Error("The display-brand instruction CSV header is invalid.");
}

const assetNames = instructionRows.map((row) => {
  if (row.length !== 3 || !row[0]) {
    throw new Error(`Invalid display-brand instruction row: ${row.join(",")}`);
  }
  return row[0];
});
if (assetNames.length !== 6 || new Set(assetNames).size !== assetNames.length) {
  throw new Error(
    "The display-brand instruction CSV must govern six unique assets.",
  );
}
const launchFlowAssetNames = assetNames
  .filter((assetName) => assetName.endsWith(".svg"))
  .sort();
if (
  launchFlowAssetNames.length !== exactLaunchFlowAssetNames.length ||
  launchFlowAssetNames.some(
    (assetName, index) => assetName !== exactLaunchFlowAssetNames[index],
  ) ||
  !assetNames.includes("Core.png") ||
  assetNames.filter((assetName) => assetName === "Core.png").length !== 1
) {
  throw new Error(
    "The current adapter must govern five LaunchFlow SVG assets while Core.png remains allocated to Phase 8.",
  );
}

const sourceDirectoryEntries = (await readdir(brandDirectory)).sort();
const expectedDirectoryEntries = [
  "Brand Asset Instruction.csv",
  ...assetNames,
].sort();
if (
  sourceDirectoryEntries.length !== expectedDirectoryEntries.length ||
  sourceDirectoryEntries.some(
    (entry, index) => entry !== expectedDirectoryEntries[index],
  )
) {
  throw new Error(
    "The display-brand source directory differs from its instruction CSV.",
  );
}

const adapterContent = await readFile(adapterFile, "utf8");
const coreSourceHash = createHash("sha256")
  .update(await readFile(path.join(brandDirectory, "Core.png")))
  .digest("hex");
const launchFlowSourceHashes = new Map();
for (const assetName of launchFlowAssetNames) {
  launchFlowSourceHashes.set(
    assetName,
    createHash("sha256")
      .update(await readFile(path.join(brandDirectory, assetName)))
      .digest("hex"),
  );
  const governedReference = `../../../docs/Brand Asset/${assetName}?no-inline`;
  const referenceCount = adapterContent.split(governedReference).length - 1;
  if (referenceCount !== 1) {
    throw new Error(
      `${assetName} must have one direct, non-inline adapter reference; found ${referenceCount}.`,
    );
  }
}

const sourceTreeFiles = await collectFiles(path.join(frontendRoot, "src"), [
  "",
]);
await assertOnlyApprovedStaticAssets(sourceTreeFiles, {
  allowedRelativePaths: ["generated/.gitkeep"],
  allowedTextExtensions: [".css", ".ts", ".tsx"],
  label: "The R1-02 frontend source tree",
  relativeTo: path.join(frontendRoot, "src"),
});

const indexContent = await readFile(indexFile, "utf8");
const staticFaviconReference =
  "../docs/Brand Asset/LaunchFlow Icon.svg?no-inline";
if (
  indexContent.split(staticFaviconReference).length - 1 !== 1 ||
  indexContent.split('data-brand-context="favicon"').length - 1 !== 1 ||
  indexContent.split('data-brand-asset="LaunchFlow Icon.svg"').length - 1 !== 1
) {
  throw new Error(
    "The entry HTML must provide one exact, auditable LaunchFlow favicon before React starts.",
  );
}

const applicationFiles = [
  ...(await collectFiles(path.join(frontendRoot, "src"), [
    ".css",
    ".json",
    ".ts",
    ".tsx",
  ])),
  indexFile,
  viteConfigFile,
  ...(await collectOptionalFiles(publicDirectory, [
    ".css",
    ".html",
    ".js",
    ".json",
    ".mjs",
    ".svg",
    ".ts",
    ".tsx",
    ".webmanifest",
  ])),
];
for (const file of applicationFiles) {
  const content = await readFile(file, "utf8");
  if (/data:image|base64,/iu.test(content)) {
    throw new Error(
      `Display-brand image data must not be embedded in application source: ${path.relative(repositoryRoot, file)}`,
    );
  }
  if (/core\.png/iu.test(content)) {
    throw new Error(
      `Core.png is approved input for Phase 8 and must not be activated in R1-02: ${path.relative(repositoryRoot, file)}`,
    );
  }
  if (file === adapterFile) continue;
  if (
    file === indexFile &&
    content.split("docs/Brand Asset/").length - 1 === 1 &&
    content.includes(staticFaviconReference)
  ) {
    continue;
  }
  if (content.includes("docs/Brand Asset/")) {
    throw new Error(
      `Display-brand asset paths must remain centralized: ${path.relative(repositoryRoot, file)}`,
    );
  }
}

const publicFiles = await collectOptionalFiles(publicDirectory, [""]);
await assertOnlyApprovedStaticAssets(publicFiles, {
  label: "The R1-02 public tree",
  relativeTo: publicDirectory,
});
await assertNoDeferredCoreAssets(publicFiles, {
  expectedHash: coreSourceHash,
  label: "The R1-02 public tree",
  relativeTo: repositoryRoot,
});

const emittedFiles = await collectFiles(distDirectory, [""]);
await assertOnlyApprovedStaticAssets(emittedFiles, {
  allowedHashes: [...launchFlowSourceHashes.values()],
  allowedTextExtensions: [".css", ".html", ".js"],
  label: "The R1-02 production output",
  relativeTo: distDirectory,
});
await assertNoDeferredCoreAssets(emittedFiles, {
  expectedHash: coreSourceHash,
  label: "The R1-02 production output",
  relativeTo: repositoryRoot,
});
const emittedByHash = new Map();
for (const file of emittedFiles) {
  const hash = createHash("sha256")
    .update(await readFile(file))
    .digest("hex");
  const matches = emittedByHash.get(hash) ?? [];
  matches.push(file);
  emittedByHash.set(hash, matches);
}

const emittedTextFiles = await collectFiles(distDirectory, [
  ".css",
  ".html",
  ".js",
  ".json",
  ".svg",
  ".webmanifest",
]);
for (const file of emittedTextFiles) {
  const content = await readFile(file, "utf8");
  if (/core\.png/iu.test(content) || content.includes(coreSourceHash)) {
    throw new Error(
      `The R1-02 production output leaks the Phase 8 Core asset identity: ${path.relative(repositoryRoot, file)}`,
    );
  }
}

for (const assetName of launchFlowAssetNames) {
  const sourceHash = launchFlowSourceHashes.get(assetName);
  if (!sourceHash) throw new Error(`Missing source hash for ${assetName}.`);
  const emittedMatches = emittedByHash.get(sourceHash) ?? [];
  if (emittedMatches.length !== 1) {
    throw new Error(
      `${assetName} must be emitted once with exact source bytes; found ${emittedMatches.length}.`,
    );
  }
}

console.log(
  `display-brand production asset audit passed (${launchFlowAssetNames.length} exact LaunchFlow SVG files; Core.png held for Phase 8)`,
);
