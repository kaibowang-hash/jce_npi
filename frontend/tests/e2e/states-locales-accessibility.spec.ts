import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import {
  coreScreens,
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  expectScenarioSurface,
  expectSinglePrimaryAction,
  locales,
  openPrototype,
  scenarios,
} from "./support";

test.describe("normal, unavailable, conflict, and asynchronous state matrix", () => {
  for (const screen of coreScreens) {
    test(`${screen.id} exposes every required deterministic state`, async ({
      page,
    }) => {
      for (const scenario of scenarios) {
        await test.step(scenario, async () => {
          await openPrototype(page, screen, { scenario });
          await expect(
            page.locator(`article.${screen.pageClass}`),
          ).toBeVisible();
          await expectScenarioSurface(page, scenario);
          await expect(page.locator("body")).not.toContainText("⟦Missing:");
        });
      }
    });
  }
});

test.describe("three-language rendering and language purity", () => {
  for (const locale of locales) {
    for (const screen of coreScreens) {
      test(`${screen.id} renders a pure ${locale} interface`, async ({
        page,
      }) => {
        await openPrototype(page, screen, { locale });
        await expectNoMixedLanguage(page, locale);
      });
    }
  }

  test("the prototype fallback persists a selected Frappe language code across refresh", async ({
    page,
  }) => {
    await page.goto("/work", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#main-content")).toBeVisible();
    const language = page.getByRole("combobox", { name: "Language" });
    await language.selectOption("zh-TW");
    await expect(page.locator("html")).toHaveAttribute("lang", "zh-TW");
    await expect(page.locator(".prototype-banner")).toContainText("原型");
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("lang", "zh-TW");
    await expectNoMixedLanguage(page, "zh-TW");
  });

  for (const locale of ["zh", "zh-TW"] as const) {
    test(`${locale} URL locale survives cross-object navigation and refresh`, async ({
      page,
    }) => {
      await openPrototype(page, "/work", { locale });
      await page.locator(".domain-navigation li:nth-child(4) button").click();
      await expect(page).toHaveURL(/\/tooling\/TL-26018-01$/);
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      await expectNoMixedLanguage(page, locale);
    });
  }
});

test.describe("WCAG and stable engineering-layout checks", () => {
  for (const screen of coreScreens) {
    test(`${screen.id} has no WCAG A/AA violations detected by axe`, async ({
      page,
    }) => {
      await openPrototype(page, screen);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(
        results.violations,
        JSON.stringify(
          results.violations.map(({ id, impact, nodes }) => ({
            id,
            impact,
            targets: nodes.map((node) => node.target),
          })),
          null,
          2,
        ),
      ).toEqual([]);
    });

    test(`${screen.id} resolves the classic light industrial token contract in the browser`, async ({
      page,
    }) => {
      await openPrototype(page, screen);
      await expectSinglePrimaryAction(page);
      await expectIndustrialComputedStyles(page);
    });

    test(`${screen.id} remains usable at required desktop sizes and zoom-equivalent layouts`, async ({
      page,
    }) => {
      const variants = [
        { height: 768, width: 1366, zoom: 1 as const },
        { height: 768, width: 1366, zoom: 1.25 as const },
        { height: 768, width: 1366, zoom: 1.5 as const },
        { height: 1080, width: 1920, zoom: 1 as const },
        { height: 1080, width: 1920, zoom: 1.25 as const },
        { height: 1080, width: 1920, zoom: 1.5 as const },
      ];
      for (const variant of variants) {
        const label = `${String(variant.width)}x${String(variant.height)} at ${String(variant.zoom * 100)}%`;
        await test.step(label, async () => {
          await page.setViewportSize(effectiveViewport(variant, variant.zoom));
          await openPrototype(page, screen);
          await expect(page.locator(".app-header")).toBeVisible();
          await expect(page.locator(".domain-navigation")).toBeVisible();
          await expect(page.locator(".status-bar")).toBeVisible();
          await expectSinglePrimaryAction(page);
          await expectNoDocumentOverflow(page);
        });
      }
    });
  }

  test("768x1024 field tablet supports Trial review, photo capture, and the primary command", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 1024, width: 768 });
    await openPrototype(page, "/trials/T1");
    const photoInput = page.locator(
      'input[type="file"][capture="environment"]',
    );
    await expect(photoInput).toBeAttached();
    await expect(photoInput).toHaveClass(/visually-hidden/);
    await expect(page.getByText("Add trial photo")).toBeVisible();
    await photoInput.setInputFiles({
      name: "trial-cavity-3.png",
      mimeType: "image/png",
      buffer: Buffer.from("phase-3-photo-fixture"),
    });
    await expect(
      page.getByText("Prototype photo selected. No file was uploaded."),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Submit trial conclusion" }),
    ).toBeVisible();
    await expectNoDocumentOverflow(page);
  });

  test("390x844 field phone supports Trial review, photo evidence, and a prepared action update", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 844, width: 390 });
    await openPrototype(page, "/trials/T1");
    await expect(
      page.getByRole("heading", {
        name: "T1 / TL-26018-01 Trial round",
      }),
    ).toBeVisible();
    await expect(page.getByText("Input versions locked")).toBeVisible();

    const photoInput = page.locator(
      'input[type="file"][capture="environment"]',
    );
    await photoInput.setInputFiles({
      name: "phone-cavity-3.png",
      mimeType: "image/png",
      buffer: Buffer.from("phase-3-phone-photo-fixture"),
    });
    await expect(
      page.getByText("Prototype photo selected. No file was uploaded."),
    ).toBeVisible();

    await page.getByRole("button", { name: "Submit trial conclusion" }).click();
    const review = page.getByRole("dialog", {
      name: "Trial conclusion impact review",
    });
    await expect(review).toBeVisible();
    await review
      .getByRole("textbox", { name: "Reason" })
      .fill("Phone field review completed");
    await review
      .getByRole("button", { name: "Prepare conclusion command" })
      .click();
    await expect(
      page.getByText(
        "Prototype conclusion command prepared. The Trial snapshot was not submitted.",
      ),
    ).toBeVisible();
    await expectNoDocumentOverflow(page);
  });
});
