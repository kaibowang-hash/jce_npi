import { expect, test, type Locator, type Page } from "@playwright/test";

import { catalogVersion } from "../../src/generated/catalog-version";
import {
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  openPrototype,
  p0VisualRegistry,
  type CoreScreen,
} from "./support";

interface SurfaceGeometry {
  height: number;
  width: number;
}

async function visibleGeometry(locator: Locator): Promise<SurfaceGeometry> {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return {
    height: box?.height ?? 0,
    width: box?.width ?? 0,
  };
}

async function expectP0Density(page: Page, screen: CoreScreen): Promise<void> {
  const pageSurface = page.locator(`.${screen.pageClass}`).first();
  const context = page.locator(screen.contextSelector).first();
  const workSurface = page.locator(screen.workSurfaceSelector).first();
  const properties = page.locator(screen.propertiesSelector).first();

  const pageGeometry = await visibleGeometry(pageSurface);
  const contextGeometry = await visibleGeometry(context);
  const workGeometry = await visibleGeometry(workSurface);
  const propertiesGeometry = await visibleGeometry(properties);

  await expect(
    page.locator('[data-visual-primary="true"]:visible'),
  ).toHaveCount(1);
  expect(pageGeometry.width).toBeGreaterThanOrEqual(1080);
  expect(contextGeometry.height).toBeLessThanOrEqual(210);
  expect(workGeometry.width).toBeGreaterThanOrEqual(560);
  expect(workGeometry.height).toBeGreaterThanOrEqual(240);
  expect(propertiesGeometry.width).toBeGreaterThanOrEqual(220);
  expect(propertiesGeometry.height).toBeGreaterThanOrEqual(180);
}

test.describe("@visual R1-06 durable 1440 P0 matrix", () => {
  for (const screen of p0VisualRegistry.screens) {
    for (const locale of p0VisualRegistry.locales) {
      const name =
        `r1-06-p0-normal-${screen.id}-${locale}-` +
        `${String(p0VisualRegistry.viewport.width)}x` +
        `${String(p0VisualRegistry.viewport.height)}-` +
        String(p0VisualRegistry.viewport.zoomPercent);

      test(name, async ({ page }) => {
        await page.setViewportSize({
          height: p0VisualRegistry.viewport.height,
          width: p0VisualRegistry.viewport.width,
        });
        await page.emulateMedia({
          colorScheme: "light",
          reducedMotion: "reduce",
        });
        await openPrototype(page, screen, {
          locale,
          scenario: p0VisualRegistry.scenario,
        });
        await expectNoMixedLanguage(page, locale);
        await expectNoDocumentOverflow(page);
        await expectP0Density(page, screen);
        const catalogFingerprint = page.locator(".status-bar__catalog code");
        await expect(catalogFingerprint).toHaveText(catalogVersion);
        await catalogFingerprint.evaluate((element, visualVersion) => {
          element.textContent = visualVersion;
        }, p0VisualRegistry.catalogVisualVersion);
        await page.addStyleTag({
          content:
            "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
        });
        await page.evaluate(async () => document.fonts.ready);
        await page.evaluate(() => {
          globalThis.scrollTo(0, 0);
        });
        await expect(page).toHaveScreenshot(`${name}.png`, {
          fullPage: false,
        });
      });
    }
  }
});
