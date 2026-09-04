import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url));
const brandAssetDirectory = path.resolve(
  frontendDirectory,
  "..",
  "docs",
  "Brand Asset",
);
const evidenceScope = process.env.NPI_EVIDENCE_SCOPE?.trim() || "phase-4";
if (
  !/^[a-z0-9]+(?:-[a-z0-9]+)*(?:\/[a-z0-9]+(?:-[a-z0-9]+)*)*$/u.test(
    evidenceScope,
  )
) {
  throw new Error("NPI_EVIDENCE_SCOPE contains an unsafe path segment.");
}

export default defineConfig({
  plugins: [react()],
  build: {
    sourcemap: false,
    target: "es2022",
  },
  server: {
    fs: {
      allow: [brandAssetDirectory, frontendDirectory],
    },
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    include: ["tests/unit/**/*.{test,spec}.{ts,tsx}"],
    setupFiles: ["./tests/setup.ts"],
    css: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary", "html"],
      reportsDirectory: `../implementation/evidence/${evidenceScope}/coverage`,
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "**/*.config.*",
        "dist/**",
        "scripts/**",
        "tests/**",
        "src/generated/**",
        "src/fixtures/**",
        "src/main.tsx",
      ],
      thresholds: {
        lines: 80,
        functions: 80,
        statements: 80,
        branches: 75,
      },
    },
  },
});
