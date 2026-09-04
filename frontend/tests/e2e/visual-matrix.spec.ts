import { expect, test, type Page } from "@playwright/test";

import {
  coreScreens,
  effectiveViewport,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  expectScenarioSurface,
  locales,
  openPrototype,
  scenarios,
  type CoreScreen,
  type TestLocale,
  type TestScenario,
} from "./support";

type Zoom = 1 | 1.25 | 1.5;

interface VisualCase {
  height: number;
  locale: TestLocale;
  name: string;
  scenario: TestScenario;
  screen: CoreScreen;
  width: number;
  zoom: Zoom;
}

const standardDesktop = { height: 768, width: 1366 };
const largeDesktop = { height: 1080, width: 1920 };

function requireScreen(id: CoreScreen["id"]): CoreScreen {
  const screen = coreScreens.find((candidate) => candidate.id === id);
  if (!screen) throw new Error(`Missing visual fixture screen: ${id}`);
  return screen;
}

const localeCases: VisualCase[] = coreScreens.flatMap((screen) =>
  locales.map((locale) => ({
    ...standardDesktop,
    locale,
    name: `locale-${screen.id}-${locale}-1366x768-100`,
    scenario: "normal",
    screen,
    zoom: 1,
  })),
);

const desktopGeometryCases: VisualCase[] = coreScreens.flatMap((screen) =>
  [
    { ...largeDesktop, zoom: 1 as const },
    { ...standardDesktop, zoom: 1.25 as const },
    { ...standardDesktop, zoom: 1.5 as const },
    { ...largeDesktop, zoom: 1.25 as const },
    { ...largeDesktop, zoom: 1.5 as const },
  ].map((geometry) => ({
    ...geometry,
    locale: "en" as const,
    name: `geometry-${screen.id}-${String(geometry.width)}x${String(geometry.height)}-${String(geometry.zoom * 100)}`,
    scenario: "normal" as const,
    screen,
  })),
);

const stateCases: VisualCase[] = coreScreens.flatMap((screen, screenIndex) =>
  scenarios
    .filter((scenario) => scenario !== "normal")
    .map((scenario, scenarioIndex) => {
      const locale =
        locales[(screenIndex + scenarioIndex) % locales.length] ?? "en";
      const geometry =
        (screenIndex + scenarioIndex) % 2 === 0
          ? standardDesktop
          : largeDesktop;
      const zoom = [1, 1.25, 1.5][
        (screenIndex * 2 + scenarioIndex) % 3
      ] as Zoom;
      return {
        ...geometry,
        locale,
        name: `state-${screen.id}-${scenario}-${locale}-${String(geometry.width)}x${String(geometry.height)}-${String(zoom * 100)}`,
        scenario,
        screen,
        zoom,
      };
    }),
);

const tabletCases: VisualCase[] = locales.map((locale) => ({
  height: 1024,
  locale,
  name: `field-tablet-trial-${locale}-768x1024-100`,
  scenario: "normal",
  screen: requireScreen("trial"),
  width: 768,
  zoom: 1,
}));

async function prepareVisualCase(
  page: Page,
  fixture: VisualCase,
): Promise<void> {
  // Browser zoom reduces the layout viewport. The inverse viewport is deterministic in
  // headless Chromium, where browser-chrome zoom shortcuts are intentionally ignored.
  await page.setViewportSize(effectiveViewport(fixture, fixture.zoom));
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "reduce" });
  await openPrototype(page, fixture.screen, {
    locale: fixture.locale,
    scenario: fixture.scenario,
  });
  await expectScenarioSurface(page, fixture.scenario);
  await expectNoMixedLanguage(page, fixture.locale);
  await expectNoDocumentOverflow(page);
  await page.addStyleTag({
    content:
      "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
  });
  await page.evaluate(async () => document.fonts.ready);
  await page.evaluate(() => {
    globalThis.scrollTo(0, 0);
  });
}

test.describe("@visual deterministic Phase 3 evidence matrix", () => {
  for (const fixture of [
    ...localeCases,
    ...desktopGeometryCases,
    ...stateCases,
    ...tabletCases,
  ]) {
    test(fixture.name, async ({ page }) => {
      await prepareVisualCase(page, fixture);
      await expect(page).toHaveScreenshot(`${fixture.name}.png`, {
        fullPage: false,
      });
    });
  }
});
