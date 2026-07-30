import { readFileSync } from "node:fs";

import { expect, type Page } from "@playwright/test";

const terminology = readFileSync(
  new URL("../../../contracts/terminology-allowlist.yaml", import.meta.url),
  "utf8",
);
const p0VisualRegistryDocument: unknown = JSON.parse(
  readFileSync(new URL("./p0-visual-registry.json", import.meta.url), "utf8"),
);

function terminologyList(name: string): string[] {
  const lines = terminology.split(/\r?\n/);
  const start = lines.findIndex((line) => line === `${name}:`);
  if (start < 0) throw new Error(`Missing terminology section: ${name}`);
  const values: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (line && !line.startsWith(" ")) break;
    const value = /^ {2}- (.+)$/.exec(line)?.[1];
    if (value) values.push(value);
  }
  return values;
}

function terminologySources(name: string): string[] {
  const lines = terminology.split(/\r?\n/);
  const start = lines.findIndex((line) => line === `${name}:`);
  if (start < 0) throw new Error(`Missing terminology section: ${name}`);
  const values: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (line && !line.startsWith(" ")) break;
    const value = /^ {2}- source: (.+)$/.exec(line)?.[1];
    if (value) values.push(value);
  }
  return values;
}

function unquoteYamlScalar(value: string): string {
  const match = /^(['"])(.*)\1$/u.exec(value);
  return match ? (match[2] ?? value) : value;
}

const retainTerms = terminologySources("retain_terms").sort(
  (left, right) => right.length - left.length,
);
const unitTokens = new Set(
  terminologyList("unit_examples").map(unquoteYamlScalar),
);

function unapprovedLatinTokens(value: string): string[] {
  let candidate = value;
  for (const term of retainTerms) {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    candidate = candidate.replace(
      new RegExp(`(^|[^A-Za-z0-9])${escaped}(?=$|[^A-Za-z0-9])`, "gu"),
      "$1",
    );
  }
  return [...candidate.matchAll(/[A-Za-z][A-Za-z0-9._/-]*/gu)]
    .map((match) => match[0])
    .filter(
      (token) =>
        !unitTokens.has(token) &&
        !/^[A-Z]$/u.test(token) &&
        !/^[A-Z][0-9]{1,4}$/u.test(token) &&
        !/^[A-Z]{2,8}-[A-Z0-9-]*[0-9][A-Z0-9-]*$/u.test(token) &&
        !/^v[0-9]+$/u.test(token),
    );
}

const forbiddenEnglishInChinese = terminologyList(
  "forbidden_general_english_in_zh_ui",
);

export const locales = ["en", "zh", "zh-TW"] as const;
export type TestLocale = (typeof locales)[number];

export const scenarios = [
  "normal",
  "loading",
  "empty",
  "no_permission",
  "read_only",
  "partial",
  "error",
  "conflict",
  "validation",
  "queued",
  "processing",
  "failed_retryable",
  "failed_final",
  "dirty",
] as const;
export type TestScenario = (typeof scenarios)[number];

export const bannerScenarios = ["read_only", "partial", "dirty"] as const;
export const terminalScenarios = [
  "empty",
  "no_permission",
  "error",
  "conflict",
  "validation",
  "queued",
  "processing",
  "failed_retryable",
  "failed_final",
] as const;

export interface CoreScreen {
  id: "work" | "project" | "gate" | "tooling" | "trial" | "execution";
  path: string;
  pageClass: string;
  contextSelector: string;
  workSurfaceSelector: string;
  propertiesSelector: string;
}

export interface P0VisualRegistry {
  schemaVersion: 1;
  viewport: {
    width: 1440;
    height: 900;
    zoomPercent: 100;
  };
  scenario: "normal";
  locales: readonly TestLocale[];
  screens: readonly CoreScreen[];
}

export const p0VisualRegistry = p0VisualRegistryDocument as P0VisualRegistry;
export const coreScreens = p0VisualRegistry.screens;

function pathWithFixture(
  path: string,
  locale: TestLocale,
  scenario: TestScenario,
): string {
  const url = new URL(path, "http://127.0.0.1:4173");
  url.searchParams.set("lang", locale);
  if (scenario !== "normal") url.searchParams.set("scenario", scenario);
  return `${url.pathname}${url.search}`;
}

export async function openPrototype(
  page: Page,
  screen: CoreScreen | string,
  options: { locale?: TestLocale; scenario?: TestScenario } = {},
): Promise<void> {
  const locale = options.locale ?? "en";
  const scenario = options.scenario ?? "normal";
  const path = typeof screen === "string" ? screen : screen.path;
  await page.goto(pathWithFixture(path, locale, scenario), {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator("#main-content")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
  await expect(page.locator(".route-loading")).toHaveCount(0);
  if (
    path.startsWith("/demo/work") &&
    ["normal", "read_only", "partial", "dirty"].includes(scenario)
  ) {
    await expect(page.locator(".worklist-panel")).toBeVisible();
    await expect(
      page.locator('.worklist-panel [aria-busy="true"]'),
    ).toHaveCount(0);
  }
}

export async function expectScenarioSurface(
  page: Page,
  scenario: TestScenario,
): Promise<void> {
  if (scenario === "normal") {
    await expect(page.locator(".state-surface")).toHaveCount(0);
    await expect(page.locator(".scenario-banner")).toHaveCount(0);
    return;
  }
  if (scenario === "loading") {
    const loading = page.locator(".state-surface--loading");
    await expect(loading).toBeVisible();
    await expect(loading).toHaveAttribute("aria-busy", "true");
    return;
  }
  if (bannerScenarios.includes(scenario as (typeof bannerScenarios)[number])) {
    await expect(page.locator(`.scenario-banner--${scenario}`)).toBeVisible();
    await expect(page.locator(".state-surface")).toHaveCount(0);
    return;
  }
  const surface = page.locator('.state-surface[role="status"]');
  await expect(surface).toBeVisible();
  await expect(surface.locator("code")).toContainText("trc-phase3-fixture");
  await expect(surface.getByRole("button")).toBeEnabled();
}

export async function textWithoutLanguageExemptions(
  page: Page,
): Promise<string> {
  return page.locator("body").evaluate((body) => {
    const values: string[] = [];
    const visibleAttributes = ["aria-label", "title", "placeholder", "alt"];
    const stripScopedTokens = (
      value: string,
      tokens: readonly string[],
    ): string =>
      [...new Set(tokens)]
        .sort((left, right) => right.length - left.length)
        .reduce((candidate, token) => {
          const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
          return candidate.replace(
            new RegExp(
              `(^|[^A-Za-z0-9._/-])${escaped}(?=$|[^A-Za-z0-9._/-])`,
              "gu",
            ),
            "$1",
          );
        }, value);
    const visit = (
      node: Node,
      inheritedExemption = false,
      inheritedTokens: readonly string[] = [],
    ): void => {
      if (node instanceof Text) {
        if (!inheritedExemption && node.textContent)
          values.push(stripScopedTokens(node.textContent, inheritedTokens));
        return;
      }
      if (!(node instanceof Element) && !(node instanceof ShadowRoot)) return;
      const element = node instanceof Element ? node : null;
      if (element?.matches("script, style")) return;
      const tokenAttribute = element?.getAttribute(
        "data-language-exempt-tokens",
      );
      const ownTokens: string[] = [];
      if (tokenAttribute) {
        const parsed: unknown = JSON.parse(tokenAttribute);
        if (!Array.isArray(parsed) || parsed.length === 0) {
          throw new Error("Invalid scoped language-exemption token list.");
        }
        for (const token of parsed as unknown[]) {
          if (
            typeof token !== "string" ||
            token.length === 0 ||
            token.trim() !== token
          ) {
            throw new Error("Invalid scoped language-exemption token list.");
          }
          ownTokens.push(token);
        }
      }
      const scopedTokens = [...inheritedTokens, ...ownTokens];
      const exempt =
        inheritedExemption ||
        element?.hasAttribute("data-language-exempt") === true;
      if (element && !exempt) {
        for (const attribute of visibleAttributes) {
          const value = element.getAttribute(attribute);
          if (value) values.push(stripScopedTokens(value, scopedTokens));
        }
      }
      if (element?.shadowRoot) {
        for (const child of element.shadowRoot.childNodes)
          visit(child, exempt, scopedTokens);
      }
      for (const child of node.childNodes) visit(child, exempt, scopedTokens);
    };
    visit(body);
    return values.join(" ").replace(/\s+/g, " ").trim();
  });
}

export async function expectNoMixedLanguage(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  const text = await textWithoutLanguageExemptions(page);
  expect(text).not.toContain("⟦Missing:");
  if (locale === "en") {
    expect(text).not.toMatch(/[\u3400-\u9fff\uf900-\ufaff]/u);
    return;
  }
  for (const word of forbiddenEnglishInChinese) {
    expect(text, `ordinary English residual in ${locale}: ${word}`).not.toMatch(
      new RegExp(`\\b${word}\\b`, "iu"),
    );
  }
  expect(
    unapprovedLatinTokens(text),
    `unapproved Latin residuals in ${locale}`,
  ).toEqual([]);
}

export async function expectSinglePrimaryAction(page: Page): Promise<void> {
  await expect(
    page.locator('[data-visual-primary="true"]:visible'),
  ).toHaveCount(1);
}

export async function expectIndustrialComputedStyles(
  page: Page,
): Promise<void> {
  const firstIxButton = page.locator("ix-button.npi-button").first();
  await expect(firstIxButton).toBeVisible();
  await expect
    .poll(() =>
      firstIxButton.evaluate((element) =>
        Boolean(element.shadowRoot?.querySelector("button")),
      ),
    )
    .toBe(true);
  const audit = await page.evaluate(() => {
    const failures: string[] = [];
    const isVisible = (element: Element): element is HTMLElement =>
      element instanceof HTMLElement &&
      (element.offsetWidth > 0 ||
        element.offsetHeight > 0 ||
        element.getClientRects().length > 0);
    const parseRadius = (value: string): number =>
      Number.parseFloat(value) || 0;
    const auditSquareSurface = (element: Element, label: string): void => {
      if (!isVisible(element)) return;
      const style = getComputedStyle(element);
      for (const radius of [
        style.borderTopLeftRadius,
        style.borderTopRightRadius,
        style.borderBottomRightRadius,
        style.borderBottomLeftRadius,
      ]) {
        if (parseRadius(radius) > 2) {
          failures.push(`${label} radius resolved to ${radius}`);
        }
      }
      if (style.boxShadow !== "none") {
        failures.push(`${label} shadow resolved to ${style.boxShadow}`);
      }
    };

    for (const panel of document.querySelectorAll(".panel")) {
      auditSquareSurface(panel, "panel");
    }
    for (const control of document.querySelectorAll(
      ".page .npi-input, .page .npi-select, .attachment-truth__picker-button, .section-anchors button, .rectangular-tabs button",
    )) {
      auditSquareSurface(control, "ordinary control");
      if (isVisible(control)) {
        const height = control.getBoundingClientRect().height;
        if (height < 28 || height > 40) {
          failures.push(
            `ordinary control height resolved to ${String(height)}px`,
          );
        }
      }
    }
    for (const textarea of document.querySelectorAll(".page textarea")) {
      auditSquareSurface(textarea, "multiline control");
      if (isVisible(textarea)) {
        const height = textarea.getBoundingClientRect().height;
        if (height < 28 || height > 160) {
          failures.push(
            `multiline control height resolved to ${String(height)}px`,
          );
        }
      }
    }
    let shadowButtonCount = 0;
    for (const host of document.querySelectorAll("ix-button.npi-button")) {
      if (!isVisible(host)) continue;
      auditSquareSurface(host, "iX button host");
      const nativeButton = host.shadowRoot?.querySelector("button");
      if (!nativeButton) {
        failures.push("visible iX button has no hydrated native control");
        continue;
      }
      shadowButtonCount += 1;
      auditSquareSurface(nativeButton, "iX shadow button");
      const height = nativeButton.getBoundingClientRect().height;
      if (height < 28 || height > 40) {
        failures.push(
          `iX shadow button height resolved to ${String(height)}px`,
        );
      }
    }
    const rootStyle = getComputedStyle(document.documentElement);
    const inspectorHeader = document.querySelector(
      ".docked-inspector .panel__header, .execution-layout .panel:not(:first-child) .panel__header",
    );
    return {
      actionPrimary: rootStyle
        .getPropertyValue("--npi-color-action-primary")
        .trim()
        .toLowerCase(),
      brandPrimary: rootStyle
        .getPropertyValue("--npi-color-brand-primary")
        .trim()
        .toLowerCase(),
      colorSchema: document.documentElement.dataset.ixColorSchema,
      controlCompact: rootStyle
        .getPropertyValue("--npi-density-control-compact")
        .trim(),
      failures,
      inspectorHeaderMinHeight: inspectorHeader
        ? getComputedStyle(inspectorHeader).minHeight
        : null,
      rowCompact: rootStyle
        .getPropertyValue("--npi-density-row-compact")
        .trim(),
      rowDefault: rootStyle
        .getPropertyValue("--npi-density-row-default")
        .trim(),
      shadowButtonCount,
      theme: document.documentElement.dataset.ixTheme,
    };
  });
  expect(audit.theme).toBe("classic");
  expect(audit.colorSchema).toBe("light");
  expect(audit.actionPrimary).toBe(audit.brandPrimary);
  expect(audit.controlCompact).toBe("32px");
  expect(audit.rowCompact).toBe("32px");
  expect(audit.rowDefault).toBe("36px");
  expect(audit.inspectorHeaderMinHeight).toBe(audit.rowDefault);
  expect(audit.shadowButtonCount).toBeGreaterThan(0);
  expect(audit.failures, JSON.stringify(audit, null, 2)).toEqual([]);
}

export async function expectNoDocumentOverflow(page: Page): Promise<void> {
  await expect
    .poll(() =>
      page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      })),
    )
    .toMatchObject({
      clientWidth: expect.any(Number),
      scrollWidth: expect.any(Number),
    });
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(
    dimensions.clientWidth + 1,
  );
}

export function effectiveViewport(
  nominal: { width: number; height: number },
  zoom: 1 | 1.25 | 1.5,
): { width: number; height: number } {
  return {
    height: Math.floor(nominal.height / zoom),
    width: Math.floor(nominal.width / zoom),
  };
}
