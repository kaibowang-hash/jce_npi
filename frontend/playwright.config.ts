import { defineConfig, devices } from "@playwright/test";

const evidenceScope = process.env.NPI_EVIDENCE_SCOPE?.trim() || "phase-4";
if (
  !/^[a-z0-9]+(?:-[a-z0-9]+)*(?:\/[a-z0-9]+(?:-[a-z0-9]+)*)*$/u.test(
    evidenceScope,
  )
) {
  throw new Error("NPI_EVIDENCE_SCOPE contains an unsafe path segment.");
}
const evidenceDirectory = `../implementation/evidence/${evidenceScope}`;

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: `${evidenceDirectory}/playwright-results`,
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  workers: 2,
  reporter: [
    ["line"],
    [
      "html",
      {
        outputFolder: `${evidenceDirectory}/playwright-report`,
        open: "never",
      },
    ],
  ],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:4173",
    locale: "en-US",
    timezoneId: "UTC",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
    timeout: 120_000,
  },
  expect: {
    toHaveScreenshot: {
      animations: "disabled",
      caret: "hide",
      maxDiffPixelRatio: 0,
    },
  },
});
