import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import { translate } from "../../src/i18n/runtime";
import {
  integrationOperationCollection,
  integrationOperationDetail,
  integrationOperationItem,
  integrationOperationItems,
  integrationOperationsProjectId as projectId,
} from "../support/integration-operations-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

async function fulfillJson(
  route: Route,
  body: unknown,
  status = 200,
  idempotencyReplayed?: "true" | "false",
): Promise<void> {
  const requestId = route.request().headers()["x-request-id"] ?? "";
  expect(requestId).toMatch(requestIdPattern);
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      ...(idempotencyReplayed
        ? { "Idempotency-Replayed": idempotencyReplayed }
        : {}),
      "X-Request-ID": requestId,
      "X-Trace-ID": "trace-p8-07-integration-browser",
    },
    status,
  });
}

async function fulfillConflict(route: Route): Promise<void> {
  const requestId = route.request().headers()["x-request-id"] ?? "";
  await route.fulfill({
    body: JSON.stringify({
      type: "urn:npi:problem:integration-operation-conflict",
      title: "The integration operation changed.",
      status: 409,
      code: "INTEGRATION_OPERATION_CONFLICT",
      traceId: "trace-p8-07-command-conflict",
      retryable: false,
    }),
    headers: {
      "Content-Type": "application/problem+json",
      "X-Request-ID": requestId,
      "X-Trace-ID": "trace-p8-07-command-conflict",
    },
    status: 409,
  });
}

async function installApi(
  page: Page,
  locale: TestLocale,
  options: { act?: boolean; commandConflict?: boolean } = {},
): Promise<void> {
  await page.route(
    /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u,
    async (route) => {
      await fulfillJson(route, {
        allowedLanguages: ["en", "zh", "zh-TW"],
        catalog: { language: locale, messages: {}, version: "8".repeat(64) },
        csrfToken: "p8-07-integration-operations-browser-csrf",
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "integration.operator@example.invalid",
      });
    },
  );
  await page.route(
    /\/api\/npi\/v1\/projects\/[^/?]+\/integration-operations(?:[/?].*)?$/u,
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname;
      if (request.method() === "POST") {
        expect(request.headers()["x-frappe-csrf-token"]).toBe(
          "p8-07-integration-operations-browser-csrf",
        );
        expect(request.headers()["idempotency-key"]).toMatch(/^p807-/u);
        const replayable = integrationOperationItem("failed_retryable", 4);
        expect(request.postDataJSON()).toEqual({
          expectedRawState: replayable.rawState,
          expectedVersion: replayable.operationVersion,
        });
        if (options.commandConflict) return fulfillConflict(route);
        return fulfillJson(
          route,
          {
            actionGlobalId: "90000000-0000-4000-8000-000000000001",
            operationGlobalId: replayable.operationGlobalId,
            outcomeState: "replay_requested",
            outcomeReferenceGlobalId: replayable.operationGlobalId,
          },
          201,
          "false",
        );
      }
      expect(request.method()).toBe("GET");
      const item = integrationOperationItems().find((candidate) =>
        path.endsWith(candidate.operationGlobalId),
      );
      if (item) return fulfillJson(route, integrationOperationDetail(item));
      if (path.endsWith("/dlq")) {
        return fulfillJson(
          route,
          integrationOperationCollection({
            ...(options.act === undefined ? {} : { act: options.act }),
            items: integrationOperationItems().filter(
              (candidate) => candidate.logicalDlq,
            ),
          }),
        );
      }
      return fulfillJson(
        route,
        integrationOperationCollection(
          options.act === undefined ? {} : { act: options.act },
        ),
      );
    },
  );
}

async function openWorkspace(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(
    `/projects/${projectId}/integration-operations?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      name: translate(locale, "Project operation worklist"),
    }),
  ).toBeVisible();
  await expect(
    page.locator(".integration-operation-worklist tbody tr"),
  ).toHaveCount(10);
  await expect(page.locator(".integration-operation-inspector")).toBeVisible();
}

test.describe("P8-07 live integration operations", () => {
  test("uses Project-first reads and records only the exact replay request", async ({
    page,
  }) => {
    const requests: string[] = [];
    page.on("request", (request) => requests.push(request.url()));
    await installApi(page, "en");
    await openWorkspace(page, "en");
    const replayable = integrationOperationItem("failed_retryable", 4);

    await page
      .locator(".integration-operation-worklist")
      .getByText(replayable.operationGlobalId)
      .click();
    await expect(
      page.getByRole("button", { name: "Review and request replay" }),
    ).toBeEnabled();
    await page
      .getByRole("button", { name: "Review and request replay" })
      .click();
    const review = page.getByRole("dialog", { name: "Replay impact review" });
    await review
      .getByRole("textbox", { name: "Reason" })
      .fill("Reviewed exact immutable source");
    await review.getByRole("button", { name: "Request exact replay" }).click();
    await expect(page.getByText("Replay request recorded")).toBeVisible();
    await expect(
      page.getByText(
        "The append-only operator action is recorded. This does not confirm ERPNext completion.",
      ),
    ).toBeVisible();
    expect(
      requests.every((url) => {
        const parsed = new URL(url);
        return (
          (parsed.hostname === "127.0.0.1" ||
            parsed.hostname === "localhost") &&
          (!parsed.pathname.startsWith("/api/npi/v1/") ||
            !parsed.pathname.includes("integration-operations") ||
            parsed.pathname.startsWith(`/api/npi/v1/projects/${projectId}/`))
        );
      }),
    ).toBe(true);
  });

  test("shows the logical DLQ and keeps a stale command conflict visible", async ({
    page,
  }) => {
    await installApi(page, "en", { commandConflict: true });
    await openWorkspace(page, "en");
    await page.getByRole("button", { name: "Show logical DLQ" }).click();
    await expect(
      page.locator(".integration-operation-worklist tbody tr"),
    ).toHaveCount(6);
    const replayable = integrationOperationItem("failed_retryable", 4);
    await page
      .locator(".integration-operation-worklist")
      .getByText(replayable.operationGlobalId)
      .click();
    await page
      .getByRole("button", { name: "Review and request replay" })
      .click();
    const review = page.getByRole("dialog", { name: "Replay impact review" });
    await review
      .getByRole("textbox", { name: "Reason" })
      .fill("Review current operation state");
    await review.getByRole("button", { name: "Request exact replay" }).click();
    await expect(
      page.getByRole("heading", { name: "Command conflict" }),
    ).toBeVisible();
    await expect(page.getByText("trace-p8-07-command-conflict")).toBeVisible();
  });

  test("keeps replay visible but disabled in a read-only Project", async ({
    page,
  }) => {
    await installApi(page, "en", { act: false });
    await openWorkspace(page, "en");
    const replayable = integrationOperationItem("failed_retryable", 4);
    await page
      .locator(".integration-operation-worklist")
      .getByText(replayable.operationGlobalId)
      .click();
    await expect(page.getByText("Read-only integration view")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Review and request replay" }),
    ).toBeDisabled();
  });
});

const visualCases = [
  {
    height: 768,
    locale: "en",
    name: "p8-07-integration-operations-en-1366x768-100",
    width: 1366,
    zoom: 1,
  },
  {
    height: 900,
    locale: "zh",
    name: "p8-07-integration-operations-zh-1440x900-125",
    width: 1440,
    zoom: 1.25,
  },
  {
    height: 1080,
    locale: "zh-TW",
    name: "p8-07-integration-operations-zh-TW-1920x1080-150",
    width: 1920,
    zoom: 1.5,
  },
] as const;

test.describe("@visual P8-07 integration operations", () => {
  for (const visual of visualCases) {
    test(visual.name, async ({ page }) => {
      await installApi(page, visual.locale);
      await page.setViewportSize(
        effectiveViewport(
          { height: visual.height, width: visual.width },
          visual.zoom,
        ),
      );
      await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
      });
      await openWorkspace(page, visual.locale);
      const replayable = integrationOperationItem("failed_retryable", 4);
      await page
        .locator(".integration-operation-worklist")
        .getByText(replayable.operationGlobalId)
        .click();
      await expect(
        page.getByRole("button", {
          name: translate(visual.locale, "Review and request replay"),
        }),
      ).toBeEnabled();
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      const results = await new AxeBuilder({ page })
        .include(".page--execution")
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(results.violations).toEqual([]);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      await expect(page).toHaveScreenshot(`${visual.name}.png`, {
        fullPage: false,
      });
    });
  }
});
