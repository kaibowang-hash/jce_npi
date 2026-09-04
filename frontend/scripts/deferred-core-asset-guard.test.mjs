import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import {
  assertNoDeferredCoreAssets,
  assertOnlyApprovedStaticAssets,
} from "./deferred-core-asset-guard.mjs";

async function fixture(t) {
  const directory = await mkdtemp(
    path.join(tmpdir(), "npi-deferred-core-guard-"),
  );
  t.after(async () => {
    await rm(directory, { recursive: true });
  });
  return directory;
}

test("rejects exact Core bytes after an extension-changing rename", async (t) => {
  const directory = await fixture(t);
  const payload = Buffer.from("exact deferred Core fixture");
  const renamed = path.join(directory, "approved-platform.bin");
  await writeFile(renamed, payload);

  await assert.rejects(
    assertNoDeferredCoreAssets([renamed], {
      expectedHash: createHash("sha256").update(payload).digest("hex"),
      label: "fixture output",
      relativeTo: directory,
    }),
    /exact deferred Core asset bytes/u,
  );
});

test("rejects a case-insensitive Core stem even when bytes change", async (t) => {
  const directory = await fixture(t);
  const optimized = path.join(directory, "CORE.WebP");
  await writeFile(optimized, "optimized deferred Core fixture");

  await assert.rejects(
    assertNoDeferredCoreAssets([optimized], {
      expectedHash: "0".repeat(64),
      label: "fixture output",
      relativeTo: directory,
    }),
    /deferred Core\.\* asset name/u,
  );
});

test("allows an unrelated binary with a different name and hash", async (t) => {
  const directory = await fixture(t);
  const unrelated = path.join(directory, "unrelated.bin");
  await writeFile(unrelated, "unrelated fixture");

  await assert.doesNotReject(
    assertNoDeferredCoreAssets([unrelated], {
      expectedHash: "0".repeat(64),
      label: "fixture output",
      relativeTo: directory,
    }),
  );
});

test("rejects a changed-byte renamed binary outside the approved static manifest", async (t) => {
  const directory = await fixture(t);
  const renamedDerivative = path.join(directory, "approved-platform.bin");
  await writeFile(
    renamedDerivative,
    "changed deferred Core derivative fixture",
  );

  await assert.rejects(
    assertOnlyApprovedStaticAssets([renamedDerivative], {
      allowedHashes: [],
      label: "fixture source tree",
      relativeTo: directory,
    }),
    /unapproved static or binary asset/u,
  );
});

test("allows only an exact approved binary hash and valid UTF-8 text", async (t) => {
  const directory = await fixture(t);
  const approved = path.join(directory, "approved.svg");
  const source = path.join(directory, "source.ts");
  await writeFile(approved, "approved exact asset");
  await writeFile(source, "export const value = true;\n");

  await assert.doesNotReject(
    assertOnlyApprovedStaticAssets([approved, source], {
      allowedHashes: [
        createHash("sha256").update("approved exact asset").digest("hex"),
      ],
      allowedTextExtensions: [".ts"],
      label: "fixture source tree",
      relativeTo: directory,
    }),
  );
});
