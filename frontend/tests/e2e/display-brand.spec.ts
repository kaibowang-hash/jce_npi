import { createHash } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

import {
  effectiveViewport,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  openPrototype,
  type TestLocale,
} from "./support";

const assetHashes: Readonly<Record<string, string>> = {
  "Company LOGO.svg":
    "856237b6bb2a9fb2d3674c7ede318eb8e3630a0ab12c451d64a25122e272a8ff",
  "LaunchFlow Icon.svg":
    "bddf68cb729a1da8378dfdc1136173b6a014706fec6b58e8421d0f4ae8892452",
  "LaunchFlow-logo_Standard.svg":
    "d2397fc9a21067a78655e9e84c4645a22cd1e4cc88835f665f7cbb7a29f6e2b6",
  "LaunchFlow-logo_White.svg":
    "55b9ab1e7b4ab9330acfc73c2ddb099db38c865d0704781f256c2cf113d4226d",
  "Loading.svg":
    "730e9e621881afbc1d3cb8520792b2ddc75f6b9dc4035311599a105a934cc253",
  "Core.png":
    "0c7182882022cf190925c90f0004c77aaca4dd513b86ccd0f23efb30171e0e42",
};

const localeCopy: Readonly<
  Record<
    TestLocale,
    {
      company: string;
      core: string;
      erpWorkItem: string;
      home: string;
      loading: string;
      platform: string;
    }
  >
> = {
  en: {
    company: "Company ownership mark",
    core: "JCE Core",
    erpWorkItem: "Tool asset creation failed",
    home: "Open LaunchFlow home",
    loading: "Loading LaunchFlow",
    platform: "LaunchFlow platform",
  },
  zh: {
    company: "公司所有权标识",
    core: "JCE Core",
    erpWorkItem: "模具资产创建失败",
    home: "打开 LaunchFlow 首页",
    loading: "正在加载 LaunchFlow",
    platform: "LaunchFlow 平台",
  },
  "zh-TW": {
    company: "公司所有權標識",
    core: "JCE Core",
    erpWorkItem: "模具資產建立失敗",
    home: "開啟 LaunchFlow 首頁",
    loading: "正在載入 LaunchFlow",
    platform: "LaunchFlow 平台",
  },
};

async function expectExactAsset(page: Page, locator: Locator): Promise<void> {
  const documentName = await locator.getAttribute("data-brand-asset");
  const source =
    (await locator.getAttribute("src")) ?? (await locator.getAttribute("href"));
  expect(documentName).not.toBeNull();
  expect(source).not.toBeNull();
  const expectedHash = definedHash(assetHashes[documentName ?? ""]);
  const response = await page.request.get(
    new URL(source ?? "", page.url()).toString(),
  );
  expect(response.ok()).toBe(true);
  const actualHash = createHash("sha256")
    .update(await response.body())
    .digest("hex");
  expect(actualHash).toBe(expectedHash);
}

function definedHash(value: string | undefined): string {
  if (!value) throw new Error("The browser referenced an unapproved asset.");
  return value;
}

async function expectBrandImagesDecoded(page: Page): Promise<void> {
  await expect
    .poll(() =>
      page
        .locator("img[data-brand-asset]")
        .evaluateAll((images) =>
          images.every(
            (image) =>
              image instanceof HTMLImageElement &&
              image.complete &&
              image.naturalWidth > 0,
          ),
        ),
    )
    .toBe(true);
}

async function selectErpSourceWorkItem(
  page: Page,
  locale: TestLocale,
): Promise<{ identities: Locator; inspector: Locator }> {
  const row = page
    .locator(".worklist-panel tbody tr")
    .filter({ hasText: localeCopy[locale].erpWorkItem });
  await expect(row).toHaveCount(1);
  await row.click();
  const inspector = page.locator(".worklist-layout > .docked-inspector");
  await expect(inspector).toBeVisible();
  const identities = inspector.getByRole("img", {
    name: localeCopy[locale].core,
  });
  await expect(identities).toHaveCount(2);
  return { identities, inspector };
}

for (const locale of ["en", "zh", "zh-TW"] as const) {
  test(`uses the exact Loading asset only for the ${locale} pre-Shell bootstrap`, async ({
    page,
  }) => {
    let releaseBootstrap: (() => void) | undefined;
    const holdBootstrap = new Promise<void>((resolve) => {
      releaseBootstrap = () => {
        resolve();
      };
    });
    await page.route("**/api/npi/v1/session/bootstrap", async (route) => {
      await holdBootstrap;
      await route.abort();
    });

    await page.goto(`/demo/work?lang=${locale}`, {
      waitUntil: "domcontentloaded",
    });
    const loading = page.getByRole("status", {
      name: localeCopy[locale].loading,
    });
    await expect(loading).toBeVisible();
    await expect(loading).toHaveAttribute("aria-busy", "true");
    await expect(loading).toHaveCSS("background-color", "rgb(23, 33, 38)");
    await expect(loading).toContainText(localeCopy[locale].loading);
    await expectExactAsset(
      page,
      loading.locator('[data-brand-context="entry-loading"]'),
    );

    if (!releaseBootstrap) {
      throw new Error("The localization bootstrap gate was not initialized.");
    }
    releaseBootstrap();
    await expect(page.locator(".app-shell")).toBeVisible();
    await expect(
      page.locator('[data-brand-context="entry-loading"]'),
    ).toHaveCount(0);
    await expect(
      page.locator(
        '.route-loading [data-brand-context="entry-loading"], .state-surface [data-brand-context="entry-loading"]',
      ),
    ).toHaveCount(0);
  });
}

for (const locale of ["en", "zh", "zh-TW"] as const) {
  test(`renders the governed Shell and source brand accessibly in ${locale}`, async ({
    page,
  }) => {
    await openPrototype(page, "/demo/projects/PJ-26018", { locale });
    await expect(page).toHaveTitle("LaunchFlow");

    const brandButton = page.getByRole("button", {
      name: localeCopy[locale].home,
    });
    await expect(brandButton).toBeVisible();
    await expect(brandButton).toHaveCSS("background-color", "rgb(23, 33, 38)");
    const darkWordmark = brandButton.locator(
      '[data-brand-context="wordmark-dark"]',
    );
    await expect(darkWordmark).toHaveAttribute(
      "data-brand-asset",
      "LaunchFlow-logo_White.svg",
    );

    const footer = page.locator("footer.status-bar");
    await expect(footer).toHaveCSS("background-color", "rgb(243, 245, 246)");
    const lightWordmark = footer.getByRole("img", { name: "LaunchFlow" });
    const companyMark = footer.getByRole("img", {
      name: localeCopy[locale].company,
    });
    await expect(lightWordmark).toHaveAttribute(
      "data-brand-context",
      "wordmark-light",
    );
    await expect(companyMark).toHaveAttribute(
      "data-brand-context",
      "company-footer",
    );

    const sourceIcon = page
      .locator(".source-badge")
      .getByRole("img", { name: localeCopy[locale].platform })
      .first();
    await expect(sourceIcon).toHaveAttribute(
      "data-brand-context",
      "platform-source",
    );
    await sourceIcon.focus();
    const sourceTooltip = sourceIcon.locator("xpath=following-sibling::*");
    await expect(sourceTooltip).toHaveAttribute("role", "tooltip");
    await expect(sourceTooltip).toHaveText(localeCopy[locale].platform);
    await expect(sourceTooltip).toBeVisible();

    const favicon = page.locator(
      'head link[rel~="icon"][data-brand-context="favicon"]',
    );
    await expect(favicon).toHaveAttribute(
      "data-brand-asset",
      "LaunchFlow Icon.svg",
    );

    await expectExactAsset(page, darkWordmark);
    await expectExactAsset(page, lightWordmark);
    await expectExactAsset(page, companyMark);
    await expectExactAsset(page, sourceIcon);
    await expectExactAsset(page, favicon);
    await expectNoMixedLanguage(page, locale);
    await expectNoDocumentOverflow(page);

    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);

    await brandButton.click();
    await expect(page).toHaveURL(/\/work(?:\?|$)/u);
  });
}

test("uses the platform icon while preserving company ownership at the compact breakpoint", async ({
  page,
}) => {
  await page.setViewportSize({ height: 768, width: 700 });
  await openPrototype(page, "/demo/projects/PJ-26018", { locale: "zh" });

  const brandButton = page.getByRole("button", {
    name: localeCopy.zh.home,
  });
  const darkWordmark = brandButton.locator(
    '[data-brand-context="wordmark-dark"]',
  );
  const compactIcon = brandButton.locator(
    '[data-brand-context="platform-source"]',
  );
  await expect(darkWordmark).toBeHidden();
  await expect(compactIcon).toBeVisible();

  const companyMark = page
    .locator("footer.status-bar")
    .getByRole("img", { name: localeCopy.zh.company });
  await expect(companyMark).toBeVisible();
  await expectExactAsset(page, compactIcon);
  await expectExactAsset(page, companyMark);
  await expectNoDocumentOverflow(page);
});

const erpIdentityProfiles = [
  { locale: "en", nominal: { height: 768, width: 1366 }, zoom: 1 },
  { locale: "zh", nominal: { height: 900, width: 1440 }, zoom: 1.25 },
  { locale: "zh-TW", nominal: { height: 1080, width: 1920 }, zoom: 1.5 },
] as const;

for (const profile of erpIdentityProfiles) {
  test(`renders the governed JCE Core source identity in ${profile.locale} @visual`, async ({
    page,
  }) => {
    await page.setViewportSize(
      effectiveViewport(profile.nominal, profile.zoom),
    );
    await openPrototype(page, "/demo/work", { locale: profile.locale });
    const { identities, inspector } = await selectErpSourceWorkItem(
      page,
      profile.locale,
    );
    for (let index = 0; index < 2; index += 1) {
      const identity = identities.nth(index);
      await expect(identity).toHaveAttribute(
        "data-brand-context",
        "erp-source",
      );
      await expect(identity).toHaveAttribute("data-brand-asset", "Core.png");
      await expectExactAsset(page, identity);
    }
    const keyboardIdentity = identities.first();
    await keyboardIdentity.focus();
    await expect(
      keyboardIdentity.locator("xpath=following-sibling::*"),
    ).toHaveText(localeCopy[profile.locale].core);
    await expect(
      keyboardIdentity.locator("xpath=following-sibling::*"),
    ).toBeVisible();
    await keyboardIdentity.evaluate((element) => {
      if (element instanceof HTMLElement) element.blur();
    });
    await expectBrandImagesDecoded(page);
    await expectNoMixedLanguage(page, profile.locale);
    await expectNoDocumentOverflow(page);
    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
    await expect(inspector).toHaveScreenshot(
      `p8-09-jce-core-identity-${profile.locale}-${String(profile.nominal.width)}x${String(profile.nominal.height)}-${String(profile.zoom * 100)}.png`,
      { animations: "disabled" },
    );
  });
}

test("keeps the JCE Core identity legible on a controlled dark source surface @visual", async ({
  page,
}) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await openPrototype(page, "/demo/work", { locale: "en" });
  const { identities } = await selectErpSourceWorkItem(page, "en");
  const sourceIdentity = identities.last();
  const sourceBadge = sourceIdentity.locator(
    "xpath=ancestor::span[contains(concat(' ', normalize-space(@class), ' '), ' source-badge ')][1]",
  );
  await sourceBadge.evaluate((element) => {
    if (!(element instanceof HTMLElement)) return;
    element.style.backgroundColor = "rgb(23, 33, 38)";
    element.style.borderColor = "rgb(107, 121, 128)";
    element.style.color = "rgb(243, 245, 246)";
    element.style.padding = "8px";
  });
  await expectExactAsset(page, sourceIdentity);
  await expectBrandImagesDecoded(page);
  await expect(sourceBadge).toHaveScreenshot(
    "p8-09-jce-core-dark-en-1440x900-100.png",
    { animations: "disabled" },
  );
});

const visualProfiles = [
  { locale: "en", nominal: { height: 768, width: 1366 }, zoom: 1 },
  { locale: "zh", nominal: { height: 900, width: 1440 }, zoom: 1 },
  { locale: "zh-TW", nominal: { height: 1080, width: 1920 }, zoom: 1 },
  { locale: "en", nominal: { height: 1080, width: 1920 }, zoom: 1.25 },
  { locale: "zh", nominal: { height: 1080, width: 1920 }, zoom: 1.5 },
  { locale: "zh-TW", nominal: { height: 768, width: 1366 }, zoom: 1.5 },
] as const;

test("shows the keyboard source tooltip in the industrial Shell @visual", async ({
  page,
}) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await openPrototype(page, "/demo/projects/PJ-26018", { locale: "en" });
  await expectBrandImagesDecoded(page);
  const sourceIcon = page
    .locator(".source-badge")
    .getByRole("img", { name: localeCopy.en.platform })
    .first();
  await sourceIcon.focus();
  await expect(sourceIcon.locator("xpath=following-sibling::*")).toBeVisible();
  await expectNoDocumentOverflow(page);
  await expect(page).toHaveScreenshot(
    "r1-02-launchflow-source-tooltip-en-1440x900-100.png",
    { fullPage: false },
  );
});

for (const profile of visualProfiles) {
  test(`LaunchFlow Shell ${profile.locale} ${String(profile.nominal.width)}x${String(profile.nominal.height)} ${String(profile.zoom * 100)}% @visual`, async ({
    page,
  }) => {
    await page.setViewportSize(
      effectiveViewport(profile.nominal, profile.zoom),
    );
    await openPrototype(page, "/demo/projects/PJ-26018", {
      locale: profile.locale,
    });
    await expectBrandImagesDecoded(page);
    await expectNoDocumentOverflow(page);
    await expect(page).toHaveScreenshot(
      `r1-02-launchflow-shell-${profile.locale}-${String(profile.nominal.width)}x${String(profile.nominal.height)}-${String(profile.zoom * 100)}.png`,
      { fullPage: false },
    );
  });
}
