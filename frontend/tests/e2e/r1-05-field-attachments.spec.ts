import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type Locator,
  type Page,
  type Route,
} from "@playwright/test";

import { isGateReviewResponseForRoute } from "../../src/api/gate-review-data-source";
import type {
  GateEvidenceScanState,
  GateRequirementEvidenceState,
  GateReviewViewModel,
} from "../../src/domain/view-models";
import { translate } from "../../src/i18n/runtime";
import { gateReviewFixture } from "../support/gate-review-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  openPrototype,
  type TestLocale,
} from "./support";

const projectGlobalId = "11111111-1111-4111-8111-111111111111";
const gateGlobalId = "44444444-4444-4444-8444-444444444444";
const csrfToken = "c".repeat(32);
const registeredObjectHash = "4".repeat(64);
const registeredFileName = "SYN-DIMENSIONAL-REPORT.pdf";
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const reviewEndpoint =
  /\/api\/npi\/v1\/projects\/[^/?]+\/gates\/[^/?]+\/review(?:\?.*)?$/u;
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const scanEvidenceState = {
  clean: "scan_clean",
  failed: "scan_failed",
  infected: "scan_infected",
  pending: "scan_pending",
} as const satisfies Readonly<
  Record<GateEvidenceScanState, GateRequirementEvidenceState>
>;
const scanLabelSource = {
  clean: "No threat found",
  failed: "Scan failed",
  infected: "Threat detected",
  pending: "Scan pending",
} as const satisfies Readonly<Record<GateEvidenceScanState, string>>;

interface GateAttachmentCase {
  readonly canAttachEvidence: boolean;
  readonly scanState: GateEvidenceScanState;
}

function requestId(route: Route): string {
  const value = route.request().headers()["x-request-id"] ?? "";
  expect(value).toMatch(requestIdPattern);
  return value;
}

function expectSafeGet(route: Route): void {
  const request = route.request();
  const headers = request.headers();
  expect(request.method()).toBe("GET");
  expect(headers.accept).toBe("application/json, application/problem+json");
  expect(headers["x-frappe-csrf-token"]).toBeUndefined();
  expect(headers["idempotency-key"]).toBeUndefined();
  requestId(route);
}

async function fulfillApi(
  route: Route,
  body: unknown,
  traceId: string,
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      "X-Request-ID": requestId(route),
      "X-Trace-ID": traceId,
    },
    status: 200,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    expectSafeGet(route);
    await fulfillApi(
      route,
      {
        allowedLanguages: ["en", "zh", "zh-TW"],
        catalog: {
          language: locale,
          messages: {},
          version: "f".repeat(64),
        },
        csrfToken,
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "reviewer@example.invalid",
      },
      "trace-r1-05-field-attachment-session",
    );
  });
}

function gateReviewWithRegisteredFile(
  scanState: GateEvidenceScanState,
  canAttachEvidence: boolean,
): GateReviewViewModel {
  const fixture = gateReviewFixture();
  const evidence: GateReviewViewModel["evidence"] = {
    ...fixture.evidence,
    permissions: {
      ...fixture.evidence.permissions,
      canAttachEvidence,
    },
    requirements: fixture.evidence.requirements.map((requirement) =>
      requirement.key === "DIMENSIONAL_REPORT"
        ? {
            ...requirement,
            evidence: requirement.evidence.map((reference) => ({
              ...reference,
              ...(reference.file
                ? {
                    file: {
                      ...reference.file,
                      scanState,
                    },
                  }
                : {}),
            })),
            evidenceState: scanEvidenceState[scanState],
          }
        : requirement,
    ),
    summary: {
      ...fixture.evidence.summary,
      unsafeScanCount: scanState === "clean" ? 0 : 1,
    },
  };
  const view = { ...fixture, evidence };
  expect(
    isGateReviewResponseForRoute(view, projectGlobalId, gateGlobalId),
  ).toBe(true);
  return view;
}

async function installGateReview(
  page: Page,
  view: GateReviewViewModel,
): Promise<void> {
  await page.route(reviewEndpoint, async (route) => {
    expectSafeGet(route);
    await fulfillApi(route, view, "trace-r1-05-field-attachment-gate");
  });
}

async function openRegisteredAttachment(
  page: Page,
  locale: TestLocale,
): Promise<Locator> {
  await page.goto(
    `/projects/${projectGlobalId}/gates/${gateGlobalId}?lang=${locale}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(
    page.getByRole("table", {
      name: translate(locale, "Frozen Gate requirements"),
    }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: /DIMENSIONAL_REPORT Synthetic dimensional report/u,
    })
    .click();
  const truth = page.locator("section.attachment-truth__registered");
  await expect(truth).toBeVisible();
  await expect(truth).toHaveAttribute(
    "aria-label",
    translate(locale, "Registered attachment truth"),
  );
  await truth.scrollIntoViewIfNeeded();
  return truth;
}

function exactTextPattern(value: string): RegExp {
  const escaped = value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
  return new RegExp(`^\\s*${escaped}\\s*$`, "u");
}

function definitionValue(
  scope: Locator,
  locale: TestLocale,
  labelSource: string,
): Locator {
  return scope
    .locator("dt")
    .filter({ hasText: exactTextPattern(translate(locale, labelSource)) })
    .locator("xpath=following-sibling::dd[1]");
}

function trialFilePicker(page: Page, locale: TestLocale): Locator {
  return page.getByLabel(translate(locale, "Choose a local file"), {
    exact: true,
  });
}

function trialDropRegion(page: Page, locale: TestLocale): Locator {
  return page.getByLabel(
    translate(locale, "Drop a file for {{field}}", {
      field: translate(locale, "Trial photo evidence"),
    }),
    { exact: true },
  );
}

function trialAttachmentField(page: Page, locale: TestLocale): Locator {
  return page.getByRole("group", {
    name: translate(locale, "Trial photo evidence"),
    exact: true,
  });
}

async function expectNoPrivateFileExposure(page: Page): Promise<void> {
  const exposure = await page.locator("body").evaluate((body) => {
    const rawPrivatePath = "/private/files/";
    const resourceAttributes = Array.from(
      body.querySelectorAll<HTMLElement>("[href], [src]"),
    ).flatMap((element) =>
      ["href", "src"].flatMap((attribute) => {
        const value = element.getAttribute(attribute);
        return value === null ? [] : [value];
      }),
    );
    return {
      privateResourceAttributes: resourceAttributes.filter((value) =>
        value.includes(rawPrivatePath),
      ),
      rawPrivatePathInMarkup: body.innerHTML.includes(rawPrivatePath),
    };
  });
  expect(exposure).toEqual({
    privateResourceAttributes: [],
    rawPrivatePathInMarkup: false,
  });
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

async function expectSurfaceQuality(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  await expectNoMixedLanguage(page, locale);
  await expectNoDocumentOverflow(page);
  await expectIndustrialComputedStyles(page);
  await expectAxeClean(page);
}

async function expectSquareFlatSurface(surface: Locator): Promise<void> {
  const style = await surface.evaluate((element) => {
    const computed = getComputedStyle(element);
    return {
      borderBottomLeftRadius: Number.parseFloat(
        computed.borderBottomLeftRadius,
      ),
      borderBottomRightRadius: Number.parseFloat(
        computed.borderBottomRightRadius,
      ),
      borderTopLeftRadius: Number.parseFloat(computed.borderTopLeftRadius),
      borderTopRightRadius: Number.parseFloat(computed.borderTopRightRadius),
      boxShadow: computed.boxShadow,
    };
  });
  expect(style.boxShadow).toBe("none");
  expect(
    Math.max(
      style.borderBottomLeftRadius,
      style.borderBottomRightRadius,
      style.borderTopLeftRadius,
      style.borderTopRightRadius,
    ),
  ).toBeLessThanOrEqual(2);
}

async function disableAnimationsAndWaitForFonts(page: Page): Promise<void> {
  await page.addStyleTag({
    content:
      "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
  });
  await page.evaluate(async () => document.fonts.ready);
}

async function selectTrialFile(
  page: Page,
  locale: TestLocale,
  fileName: string,
): Promise<void> {
  await trialFilePicker(page, locale).setInputFiles({
    buffer: Buffer.from("synthetic trial photo evidence"),
    mimeType: "image/jpeg",
    name: fileName,
  });
  await expect(
    page.getByText(translate(locale, "Local selection"), { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      translate(
        locale,
        "This file is selected locally and has not been uploaded.",
      ),
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    definitionValue(trialAttachmentField(page, locale), locale, "File name"),
  ).toHaveText(fileName);
}

test.describe("R1-05 field and attachment truth", () => {
  test("supports a keyboard-visible picker, clear with focus recovery, and reselection without claiming registration", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    await openPrototype(page, "/trials/T1", { locale: "en" });

    const field = page.getByRole("region", {
      name: translate("en", "Trial photo evidence"),
    });
    await expect(field).toBeVisible();
    await expect(
      field.getByText(translate("en", "Optional"), { exact: true }),
    ).toBeVisible();
    await expect(
      field.getByText(translate("en", "Editable"), { exact: true }),
    ).toBeVisible();
    await expect(definitionValue(field, "en", "Exact version")).toHaveText(
      "T1",
    );
    const picker = trialFilePicker(page, "en");
    await expect(picker).toHaveAttribute("type", "file");
    await picker.focus();
    await expect(picker).toBeFocused();

    const firstFileName = "SYN-TRIAL-PHOTO-A.jpg";
    await selectTrialFile(page, "en", firstFileName);
    const clear = page.getByRole("button", {
      name: translate("en", "Clear local selection"),
    });
    const clearAction = page.locator(
      ".attachment-truth__actions .npi-icon-action",
    );
    await expect(clearAction.locator("ix-button")).toHaveAttribute(
      "title",
      translate("en", "Clear local selection"),
    );
    await expect(clearAction).toHaveAttribute("data-icon-action", "true");
    await clear.focus();
    await expect(clear).toBeFocused();
    await expect(
      clearAction.getByRole("tooltip", {
        name: translate("en", "Clear local selection"),
      }),
    ).toBeVisible();
    await clear.press("Enter");
    await expect(page.getByText(firstFileName, { exact: true })).toHaveCount(0);
    await expect(picker).toBeFocused();

    const secondFileName = "SYN-TRIAL-PHOTO-B.jpg";
    await selectTrialFile(page, "en", secondFileName);
    await expect(
      field.getByText(translate("en", "Valid"), { exact: true }),
    ).toBeVisible();
    await expect(clear).toBeVisible();
    await expectNoPrivateFileExposure(page);
    await expectSurfaceQuality(page, "en");
  });

  test("accepts an actual browser File through the labelled drag-and-drop path", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    await openPrototype(page, "/trials/T1", { locale: "en" });
    const dropRegion = trialDropRegion(page, "en");
    await expect(dropRegion).toBeVisible();
    const dropDensity = await dropRegion.evaluate((element) => {
      const root = getComputedStyle(document.documentElement);
      return {
        minHeight: getComputedStyle(element).minHeight,
        rowDefault: root.getPropertyValue("--npi-density-row-default").trim(),
      };
    });
    expect(dropDensity).toEqual({
      minHeight: "36px",
      rowDefault: "36px",
    });

    const fileName = "SYN-TRIAL-DROP.jpg";
    const dataTransfer = await page.evaluateHandle(
      ({ name, type }) => {
        const transfer = new DataTransfer();
        transfer.items.add(
          new File(["synthetic dropped trial evidence"], name, { type }),
        );
        return transfer;
      },
      { name: fileName, type: "image/jpeg" },
    );
    await dropRegion.dispatchEvent("dragenter", { dataTransfer });
    await dropRegion.dispatchEvent("dragover", { dataTransfer });
    await dropRegion.dispatchEvent("drop", { dataTransfer });
    await dataTransfer.dispose();

    await expect(
      page.getByText(translate("en", "Local selection"), { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(
        translate(
          "en",
          "This file is selected locally and has not been uploaded.",
        ),
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      definitionValue(trialAttachmentField(page, "en"), "en", "File name"),
    ).toHaveText(fileName);
    await expect(
      page.getByRole("button", {
        name: translate("en", "Clear local selection"),
      }),
    ).toBeVisible();
    await expectSquareFlatSurface(dropRegion);
    await expectNoPrivateFileExposure(page);
  });

  test("retranslates a retained local validation failure after an in-page language change", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    await openPrototype(page, "/trials/T1", { locale: "en" });
    await trialFilePicker(page, "en").setInputFiles({
      buffer: Buffer.from("synthetic non-image trial evidence"),
      mimeType: "application/pdf",
      name: "SYN-NOT-AN-IMAGE.pdf",
    });

    const source =
      "The selected file is not an image. No transport was started.";
    await expect(
      page.getByRole("alert").getByText(translate("en", source)),
    ).toBeVisible();
    await page
      .getByRole("combobox", { name: translate("en", "Language") })
      .selectOption("zh");

    await expect(page.locator("html")).toHaveAttribute("lang", "zh");
    await expect(
      page.getByRole("alert").getByText(translate("zh", source)),
    ).toBeVisible();
    await expect(page.getByText(translate("en", source))).toHaveCount(0);
    await expectNoMixedLanguage(page, "zh");
  });

  test("keeps the field truth visible but removes picker and clear mutation paths in read-only mode", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    await openPrototype(page, "/trials/T1", {
      locale: "en",
      scenario: "read_only",
    });

    const field = page.getByRole("region", {
      name: translate("en", "Trial photo evidence"),
    });
    await expect(field).toBeVisible();
    await expect(
      field.getByText(translate("en", "Read only"), { exact: true }),
    ).toBeVisible();
    await expect(field).toContainText(
      translate("en", "The released Trial version is immutable."),
    );
    const attachment = trialAttachmentField(page, "en");
    await expect(attachment).toHaveAttribute(
      "aria-label",
      translate("en", "Trial photo evidence"),
    );
    await expect(
      attachment.getByText(
        translate("en", "This attachment field is read only."),
        {
          exact: true,
        },
      ),
    ).toBeVisible();
    await expect(trialFilePicker(page, "en")).toHaveCount(0);
    await expect(
      page.getByRole("button", {
        name: translate("en", "Clear local selection"),
      }),
    ).toHaveCount(0);
    await expectNoPrivateFileExposure(page);
    await expectSurfaceQuality(page, "en");
  });

  test("uses the industrial brand accent for actual transport progress", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    await openPrototype(page, "/trials/T1", { locale: "en" });

    const colors = await page.evaluate(() => {
      const state = document.createElement("div");
      state.className = "attachment-truth__state";
      const progress = document.createElement("progress");
      progress.max = 100;
      progress.value = 42;
      const brandProbe = document.createElement("span");
      brandProbe.style.color = "var(--npi-color-brand-primary)";
      state.append(progress);
      document.body.append(state, brandProbe);
      const result = {
        accentColor: getComputedStyle(progress).accentColor,
        brandColor: getComputedStyle(brandProbe).color,
      };
      state.remove();
      brandProbe.remove();
      return result;
    });

    expect(colors.accentColor).toBe(colors.brandColor);
  });

  const registeredCases = [
    { canAttachEvidence: true, scanState: "pending" },
    { canAttachEvidence: false, scanState: "clean" },
    { canAttachEvidence: true, scanState: "infected" },
    { canAttachEvidence: false, scanState: "failed" },
  ] as const satisfies readonly GateAttachmentCase[];

  for (const attachmentCase of registeredCases) {
    test(`renders exact ${attachmentCase.scanState} registered truth without inferring per-file permission from canAttachEvidence=${String(attachmentCase.canAttachEvidence)}`, async ({
      page,
    }) => {
      await page.setViewportSize({ height: 900, width: 1440 });
      const view = gateReviewWithRegisteredFile(
        attachmentCase.scanState,
        attachmentCase.canAttachEvidence,
      );
      await installSession(page, "en");
      await installGateReview(page, view);
      const truth = await openRegisteredAttachment(page, "en");

      await expect(truth).toContainText(
        translate("en", scanLabelSource[attachmentCase.scanState]),
      );
      await expect(definitionValue(truth, "en", "Exact revision")).toHaveText(
        "1",
      );
      await expect(definitionValue(truth, "en", "File hash")).toHaveText(
        registeredObjectHash,
      );
      await expect(definitionValue(truth, "en", "Scan observed")).toContainText(
        translate("en", "Not provided by this workspace"),
      );
      await expect(definitionValue(truth, "en", "Privacy")).toContainText(
        translate("en", "Not provided by this workspace"),
      );
      await expect(
        definitionValue(truth, "en", "Confidentiality"),
      ).toContainText(translate("en", "Not provided by this workspace"));
      await expect(definitionValue(truth, "en", "Provenance")).toContainText(
        translate("en", "Not provided by this workspace"),
      );
      await expect(
        definitionValue(truth, "en", "Preview capability"),
      ).toContainText(translate("en", "Not provided by this workspace"));
      await expect(
        definitionValue(truth, "en", "Download capability"),
      ).toContainText(translate("en", "Not provided by this workspace"));
      await expect(
        definitionValue(truth, "en", "Attachment permission"),
      ).toContainText(translate("en", "Not provided by this workspace"));
      await expect(truth).toContainText(registeredFileName);
      await expect(truth.locator("[href], [src]")).toHaveCount(0);
      await expectNoPrivateFileExposure(page);
      await expectNoMixedLanguage(page, "en");
      await expectNoDocumentOverflow(page);
      if (attachmentCase.scanState === "pending") {
        await expectIndustrialComputedStyles(page);
        await expectAxeClean(page);
      }
    });
  }
});

test.describe("@visual R1-05 field and attachment truth evidence", () => {
  test("local selection en 1366x768 100% @visual", async ({ page }) => {
    await page.setViewportSize({ height: 768, width: 1366 });
    await page.emulateMedia({
      colorScheme: "light",
      reducedMotion: "reduce",
    });
    await openPrototype(page, "/trials/T1", { locale: "en" });
    await selectTrialFile(page, "en", "SYN-TRIAL-VISUAL.jpg");
    const clearAction = page.locator(
      ".attachment-truth__actions .npi-icon-action",
    );
    await page
      .getByRole("button", {
        name: translate("en", "Clear local selection"),
      })
      .focus();
    await expect(
      clearAction.getByRole("tooltip", {
        name: translate("en", "Clear local selection"),
      }),
    ).toBeVisible();
    await expectSurfaceQuality(page, "en");
    await disableAnimationsAndWaitForFonts(page);
    const field = page.getByRole("region", {
      name: translate("en", "Trial photo evidence"),
    });
    await field.scrollIntoViewIfNeeded();
    await page.addStyleTag({
      content: ".status-bar { display: none !important; }",
    });
    await expect(field).toHaveScreenshot(
      "r1-05-field-attachment-local-en-1366x768-100.png",
      { animations: "disabled" },
    );
  });

  test("registered pending zh 1440x900 125% @visual", async ({ page }) => {
    await page.setViewportSize(
      effectiveViewport({ height: 900, width: 1440 }, 1.25),
    );
    await page.emulateMedia({
      colorScheme: "light",
      reducedMotion: "reduce",
    });
    await installSession(page, "zh");
    await installGateReview(
      page,
      gateReviewWithRegisteredFile("pending", true),
    );
    const truth = await openRegisteredAttachment(page, "zh");
    await expectSurfaceQuality(page, "zh");
    await disableAnimationsAndWaitForFonts(page);
    await truth.scrollIntoViewIfNeeded();
    await expect(truth).toHaveScreenshot(
      "r1-05-field-attachment-pending-zh-1440x900-125.png",
      { animations: "disabled" },
    );
  });

  test("registered clean permission unavailable zh-TW 1920x1080 150% @visual", async ({
    page,
  }) => {
    await page.setViewportSize(
      effectiveViewport({ height: 1080, width: 1920 }, 1.5),
    );
    await page.emulateMedia({
      colorScheme: "light",
      reducedMotion: "reduce",
    });
    await installSession(page, "zh-TW");
    await installGateReview(page, gateReviewWithRegisteredFile("clean", false));
    const truth = await openRegisteredAttachment(page, "zh-TW");
    await expectSurfaceQuality(page, "zh-TW");
    await disableAnimationsAndWaitForFonts(page);
    await truth.scrollIntoViewIfNeeded();
    await expect(truth).toHaveScreenshot(
      "r1-05-field-attachment-clean-permission-unavailable-zh-TW-1920x1080-150.png",
      { animations: "disabled" },
    );
  });
});
