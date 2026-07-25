import { expect, test } from "@playwright/test";

import {
  coreScreens,
  expectSinglePrimaryAction,
  openPrototype,
} from "./support";

test.describe("six clickable Phase 3 prototype flows", () => {
  test("My Work opens an overdue blocking Gate deliverable in context", async ({
    page,
  }) => {
    await openPrototype(page, "/demo/work");
    const item = page
      .getByRole("row")
      .filter({ hasText: "Close the major T1 flash defect" });
    await expect(item).toContainText("This blocks G5");
    await item.getByRole("button", { name: "Resolve defect" }).click();
    await expect(page).toHaveURL(/\/projects\/PJ-26018\/gates\/G5/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "G5 / PJ-26018",
    );
    await expect(page.getByText("Blocked by missing evidence")).toBeVisible();
  });

  test("Project Cockpit locates the major blocker and prepares a corrective action", async ({
    page,
  }) => {
    await openPrototype(page, "/demo/projects/PJ-26018");
    const blocker = page
      .locator(".blocking-message")
      .filter({ hasText: "T1 cavity 3 flash" });
    await expect(blocker).toBeVisible();
    await blocker
      .getByRole("button", { name: "Create corrective action" })
      .click();
    await expect(page.locator(".scenario-banner--queued")).toContainText(
      "Prototype corrective action prepared. No action was saved.",
    );
  });

  test("Tooling Cockpit reviews and prepares a design revision release", async ({
    page,
  }) => {
    await openPrototype(page, "/tooling/TL-26018-01");
    await page.getByRole("button", { name: "Release design revision" }).click();
    const review = page.getByRole("dialog", {
      name: "Tooling design release impact review",
    });
    await expect(review).toContainText("Revision C");
    await review
      .getByRole("textbox", { name: "Reason" })
      .fill("Phase 3 deterministic release review");
    await review
      .getByRole("button", { name: "Prepare release command" })
      .click();
    await expect(page.locator(".scenario-banner--queued")).toContainText(
      "Prototype release command prepared. Revision C remains unchanged.",
    );
  });

  test("Tooling Cockpit creates the next inherited Trial and exposes the round comparison", async ({
    page,
  }) => {
    await openPrototype(page, "/tooling/TL-26018-01");
    await page.getByRole("button", { name: "Create T1 from T0" }).click();
    await expect(page).toHaveURL(/\/trials\/T1\?inherit=T0/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "T1 / TL-26018-01",
    );
    await expect(page.getByText("Planned from T0")).toBeVisible();
    await page.getByRole("tab", { name: "Round comparison" }).click();
    await expect(page.getByText(/Compared with T0:/)).toBeVisible();
  });

  test("Tooling acceptance prepares an honest request and opens its ERPNext asset execution", async ({
    page,
  }) => {
    await openPrototype(page, "/tooling/TL-26018-01");
    await page
      .getByRole("button", { name: "Review tooling acceptance" })
      .click();
    const acceptance = page.getByRole("dialog", {
      name: "Tooling acceptance impact review",
    });
    await expect(acceptance).toContainText("Acceptance snapshot v1");
    await acceptance
      .getByRole("textbox", { name: "Reason" })
      .fill("Phase 3 acceptance walkthrough");
    await acceptance
      .getByRole("button", { name: "Prepare acceptance command" })
      .click();
    const prepared = page.locator(".scenario-banner--queued");
    await expect(prepared).toContainText(
      "ERPNext asset execution has not started.",
    );
    await prepared.getByRole("button", { name: "View execution" }).click();
    await expect(page).toHaveURL(/\/execution/);
    await expect(page.getByText("No formal asset was written.")).toBeVisible();
    await expect(
      page.locator(".execution-layout tbody tr").first(),
    ).toContainText("Create tool asset");
  });

  test("Project Gate track opens G6 and makes the failed formal quality result an explicit blocker", async ({
    page,
  }) => {
    await openPrototype(page, "/demo/projects/PJ-26018");
    await page.getByRole("button", { name: /G6 NPI readiness/ }).click();
    await expect(page).toHaveURL(
      /\/projects\/PJ-26018\/gates\/G6\?quality=failed/,
    );
    await expect(
      page.getByText("Blocked by formal quality result"),
    ).toBeVisible();
    await expect(page.getByText("Failed in ERPNext")).toBeVisible();
    await expect(
      page.getByText(/Readiness percentage cannot override this blocker/),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Review impact and decide" })
      .click();
    await expect(
      page.getByRole("dialog", { name: "Gate decision impact review" }),
    ).toContainText("G6 / PJ-26018");
  });
});

test.describe("primary-action and high-risk interaction invariants", () => {
  for (const screen of coreScreens) {
    test(`${screen.id} exposes exactly one visual primary action`, async ({
      page,
    }) => {
      await openPrototype(page, screen);
      await expectSinglePrimaryAction(page);
    });
  }

  test("ImpactReview manages initial focus, Escape, focus return, and the focus boundary", async ({
    page,
  }) => {
    await openPrototype(page, "/demo/projects/PJ-26018/gates/G5");
    const triggerHost = page.locator('[data-visual-primary="true"]');
    const trigger = page.getByRole("button", {
      name: "Review impact and decide",
    });
    await trigger.click();
    const dialog = page.getByRole("dialog", {
      name: "Gate decision impact review",
    });
    await expect(
      dialog.getByRole("heading", { name: "Gate decision impact review" }),
    ).toBeFocused();

    const reason = dialog.getByRole("textbox", { name: "Reason" });
    await reason.fill("Evidence reviewed");
    await reason.focus();
    await page.keyboard.press("Shift+Tab");
    const confirmHost = dialog
      .locator("ix-button")
      .filter({ hasText: "Prepare decision command" });
    await expect(confirmHost).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(triggerHost).toBeFocused();
  });

  test("worklist rows support Enter and Space selection without activating navigation", async ({
    page,
  }) => {
    await openPrototype(page, "/demo/work");
    const bodyRows = page.locator(".worklist-panel tbody tr");
    await expect(bodyRows).toHaveCount(6);
    await bodyRows.nth(1).focus();
    await expect(bodyRows.nth(1)).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(bodyRows.nth(1)).toHaveAttribute("aria-selected", "true");
    await bodyRows.nth(2).focus();
    await page.keyboard.press("Space");
    await expect(bodyRows.nth(2)).toHaveAttribute("aria-selected", "true");
    await expect(page).toHaveURL(/\/demo\/work(?:\?lang=en)?$/);
  });

  test("the real iX adapter preserves accessible names and disclosure attributes", async ({
    page,
  }) => {
    await openPrototype(page, "/execution?focus=EX-260721-0048");

    const notifications = page.getByRole("button", { name: "Notifications" });
    await expect(notifications).toHaveAttribute("aria-label", "Notifications");

    const mapping = page.getByRole("button", { name: "Open field mapping" });
    const mappingHost = page
      .locator("ix-button.npi-button")
      .filter({ hasText: "Open field mapping" });
    const mappingControl = page.locator(
      'button[aria-controls="execution-field-mapping"]',
    );
    await expect(mappingHost).not.toHaveAttribute("aria-controls");
    await expect(mappingHost).not.toHaveAttribute("aria-expanded");
    await expect(mappingControl).toHaveAttribute(
      "aria-controls",
      "execution-field-mapping",
    );
    await expect(mappingControl).toHaveAttribute("aria-expanded", "false");
    await mapping.click();
    await expect(
      page.getByRole("region", { name: "Field mapping preview" }),
    ).toBeVisible();
    await expect(mappingControl).toHaveAttribute("aria-expanded", "true");
  });

  test("dirty browser-history navigation is restored until the user reviews it", async ({
    page,
  }) => {
    await openPrototype(page, "/demo/projects/PJ-26018", {
      scenario: "dirty",
    });
    await page.evaluate(() => {
      globalThis.history.replaceState({}, "", "/work");
      globalThis.history.pushState(
        {},
        "",
        "/demo/projects/PJ-26018?lang=en&scenario=dirty",
      );
      globalThis.history.back();
    });

    const review = page.getByRole("dialog", { name: "Unsaved changes" });
    await expect(review).toBeVisible();
    await expect(page).toHaveURL(
      /\/demo\/projects\/PJ-26018\?lang=en&scenario=dirty$/,
    );
    await review.getByRole("button", { name: "Cancel" }).click();
    await expect(review).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "PJ-26018 Valve cover new tool",
    );

    await page.evaluate(() => {
      globalThis.history.back();
    });
    await expect(review).toBeVisible();
    await review
      .getByRole("textbox", { name: "Reason" })
      .fill("Discard the local browser-history draft");
    await review
      .getByRole("button", { name: "Discard changes and leave" })
      .click();
    await expect(page).toHaveURL(/\/work$/);
    await expect(page.getByRole("heading", { name: "My Work" })).toBeVisible();
  });
});
