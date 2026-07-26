import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";

function relativePath(relativeTo, file) {
  return path.relative(relativeTo, file).split(path.sep).join("/");
}

export async function assertNoDeferredCoreAssets(
  files,
  { expectedHash, label, relativeTo },
) {
  for (const file of files) {
    const relativeFile = relativePath(relativeTo, file);
    if (path.parse(file).name.toLowerCase() === "core") {
      throw new Error(
        `${label} contains a deferred Core.* asset name: ${relativeFile}`,
      );
    }
    const hash = createHash("sha256")
      .update(await readFile(file))
      .digest("hex");
    if (hash === expectedHash) {
      throw new Error(
        `${label} contains the exact deferred Core asset bytes: ${relativeFile}`,
      );
    }
  }
}

export async function assertOnlyApprovedStaticAssets(
  files,
  {
    allowedHashes = [],
    allowedRelativePaths = [],
    allowedTextExtensions = [],
    label,
    relativeTo,
  },
) {
  const approvedHashes = new Set(allowedHashes);
  const approvedRelativePaths = new Set(allowedRelativePaths);
  const approvedTextExtensions = new Set(
    allowedTextExtensions.map((extension) => extension.toLowerCase()),
  );
  const utf8Decoder = new TextDecoder("utf-8", { fatal: true });

  for (const file of files) {
    const relativeFile = relativePath(relativeTo, file);
    if (approvedRelativePaths.has(relativeFile)) continue;

    const content = await readFile(file);
    if (approvedTextExtensions.has(path.extname(file).toLowerCase())) {
      let decoded;
      try {
        decoded = utf8Decoder.decode(content);
      } catch {
        throw new Error(
          `${label} contains a non-UTF-8 file with a text extension: ${relativeFile}`,
        );
      }
      if (decoded.includes("\u0000")) {
        throw new Error(
          `${label} contains binary data with a text extension: ${relativeFile}`,
        );
      }
      continue;
    }

    const hash = createHash("sha256").update(content).digest("hex");
    if (approvedHashes.has(hash)) continue;
    throw new Error(
      `${label} contains an unapproved static or binary asset: ${relativeFile}`,
    );
  }
}
