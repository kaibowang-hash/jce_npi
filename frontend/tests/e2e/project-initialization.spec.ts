import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Route } from "@playwright/test";
import {
  projectWorkCockpitFixture,
  projectWorkContextFixture,
  projectWorkPolicyFixture,
} from "../support/project-work-fixture";
import { translate } from "../translate";
import { readinessWorkspace } from "../support/readiness-fixture";
import { expectNoDocumentOverflow, expectNoMixedLanguage } from "./support";

async function json(route: Route, body: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "private, no-store",
      "X-Request-ID": route.request().headers()["x-request-id"] ?? "",
      "X-Trace-ID": "trace-project-initialization",
    },
  });
}
for (const locale of ["en", "zh", "zh-TW"] as const) {
  test(`Project setup forms preserve industrial layout, accessibility and language in ${locale}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const context = projectWorkContextFixture();
    context.permissions.canAdminister = true;
    await page.route(/\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u, (route) =>
      json(route, {
        allowedLanguages: ["en", "zh", "zh-TW"],
        catalog: { language: locale, messages: {}, version: "5".repeat(64) },
        csrfToken: "project-initialization-browser-csrf-fixture",
        language: locale,
        preferences: { navigationCollapsed: false },
        userId: "administrator@example.invalid",
      }),
    );
    await page.route(/\/api\/npi\/v1\/projects\/[^/?]+\/cockpit$/u, (route) =>
      json(route, projectWorkCockpitFixture()),
    );
    await page.route(
      /\/api\/npi\/v1\/projects\/[^/?]+\/work-context$/u,
      (route) => json(route, context),
    );
    await page.route(
      /\/api\/npi\/v1\/projects\/[^/?]+\/npi-readiness$/u,
      (route) =>
        json(
          route,
          readinessWorkspace({
            currentRevision: null,
            revisions: [],
            sourceOptions: [],
            permissions: {
              canInitialize: true,
              canManageTemplates: true,
              canRevise: false,
            },
          }),
        ),
    );
    await page.route(
      /\/api\/npi\/v1\/npi-readiness\/templates(?:\?.*)?$/u,
      (route) =>
        json(route, { projectGlobalId: context.projectId, templates: [] }),
    );
    await page.route(
      /\/api\/npi\/v1\/projects\/[^/?]+\/setup-options$/u,
      (route) =>
        json(route, {
          projectId: context.projectId,
          projectVersion: context.projectVersion,
          nextCursor: null,
          policies: [
            {
              reference: projectWorkPolicyFixture,
              title: "Synthetic injection policy",
              roleKeys: [
                "engineering",
                "quality",
                "purchasing",
                "sales",
                "warehouse",
                "materials_control",
              ],
              wbsLifecycle: {
                initialStateKey: "not_started",
                states: [
                  {
                    key: "not_started",
                    labelSource: "Not started",
                    terminal: false,
                  },
                  {
                    key: "completed",
                    labelSource: "Completed",
                    terminal: true,
                  },
                ],
              },
            },
          ],
        }),
    );
    await page.goto(`/projects/${context.projectId}?lang=${locale}`);
    await page
      .getByRole("tab", {
        name: translate(locale, "Team and responsibilities"),
      })
      .click();
    await page
      .getByRole("button", {
        name: translate(locale, "Injection-moulding collaboration template"),
      })
      .click();
    await expect(
      page.getByLabel(translate(locale, "Template code")),
    ).toBeVisible();
    await expectNoMixedLanguage(page, locale);
    await expectNoDocumentOverflow(page);
    await page.screenshot({
      path: testInfo.outputPath(`injection-template-draft-${locale}.png`),
      fullPage: true,
    });
    await page
      .getByRole("button", {
        name: translate(locale, "Injection-moulding collaboration template"),
      })
      .click();
    await page
      .getByRole("button", {
        name: translate(locale, "Add team assignments"),
        exact: true,
      })
      .click();
    await expect(
      page.getByLabel(translate(locale, "Member email {{row}}", { row: 1 })),
    ).toBeVisible();
    await expectNoMixedLanguage(page, locale);
    await expectNoDocumentOverflow(page);
    expect(
      (
        await new AxeBuilder({ page })
          .include(".project-setup")
          .withTags(["wcag2a", "wcag2aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.screenshot({
      path: testInfo.outputPath(`project-team-setup-${locale}.png`),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: translate(locale, "Cancel"), exact: true })
      .click();
    await page
      .getByRole("tab", { name: translate(locale, "Plan"), exact: true })
      .click();
    await page
      .getByRole("button", { name: translate(locale, "Edit project plan") })
      .click();
    await expect(
      page.getByLabel(translate(locale, "Planned finish {{row}}", { row: 1 })),
    ).toBeVisible();
    await expectNoMixedLanguage(page, locale);
    await expectNoDocumentOverflow(page);
    expect(
      (
        await new AxeBuilder({ page })
          .include(".project-setup")
          .withTags(["wcag2a", "wcag2aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.screenshot({
      path: testInfo.outputPath(`project-plan-setup-${locale}.png`),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: translate(locale, "Cancel"), exact: true })
      .click();
    await page
      .getByRole("tab", {
        name: translate(locale, "NPI readiness"),
        exact: true,
      })
      .click();
    await page
      .getByRole("button", {
        name: translate(locale, "Configure readiness template"),
        exact: true,
      })
      .click();
    await expect(
      page.getByLabel(translate(locale, "Template code")),
    ).toBeVisible();
    await expectNoMixedLanguage(page, locale);
    await expectNoDocumentOverflow(page);
    expect(
      (
        await new AxeBuilder({ page })
          .include(".project-setup")
          .withTags(["wcag2a", "wcag2aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.screenshot({
      path: testInfo.outputPath(`readiness-template-setup-${locale}.png`),
      fullPage: true,
    });
    Object.assign(context, {
      initialized: false,
      workPolicyRef: null,
      members: [],
      roleAssignments: [],
      raciAssignments: [],
      substitutions: [],
      wbsItems: [],
      dependencies: [],
      baselines: [],
      baselineComparison: null,
    });
    await page.goto(`/projects/${context.projectId}?lang=${locale}&tab=team`);
    await page
      .getByRole("button", {
        name: translate(locale, "Initialize project roles"),
      })
      .click();
    await page
      .getByLabel(translate(locale, "Published work policy"))
      .selectOption(
        `${projectWorkPolicyFixture.globalId}:${String(projectWorkPolicyFixture.version)}`,
      );
    await expect(
      page.getByLabel(translate(locale, "Member email {{row}}", { row: 1 })),
    ).toHaveCount(0);
    await expectNoMixedLanguage(page, locale);
    await expectNoDocumentOverflow(page);
    await page.screenshot({
      path: testInfo.outputPath(`project-role-initialization-${locale}.png`),
      fullPage: true,
    });
  });
}
