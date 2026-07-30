import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import {
  controlledUndoPrototypeId,
  controlledUndoPrototypeStates,
} from "../../src/components/controlled-undo-prototype-model";
import { translate } from "../../src/i18n/runtime";
import {
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  openPrototype,
  type TestLocale,
} from "./support";

const prototypePath = `/demo/work?prototype=${controlledUndoPrototypeId}`;

test.describe("R1-06 controlled undo review prototype", () => {
  test("walks the closed reset and undo review states without a production command", async ({
    page,
  }) => {
    const mutationRequests: string[] = [];
    page.on("request", (request) => {
      if (
        request.url().includes("/api/npi/v1/") &&
        request.method() !== "GET"
      ) {
        mutationRequests.push(`${request.method()} ${request.url()}`);
      }
    });
    await openPrototype(page, prototypePath, { locale: "en" });
    const state = page.getByRole("region", { name: "Prototype state" });
    await expect(state).toHaveAttribute("data-prototype-state", "review");
    await expect(page.getByText("Prototype only")).toBeVisible();
    await expect(
      page.getByText("Pending Product Owner approval"),
    ).toBeVisible();

    await page.getByRole("button", { name: "Review reset" }).click();
    await expect(state).toHaveAttribute("data-prototype-state", "confirmation");
    await expect(state).toBeFocused();

    await page
      .getByRole("button", { name: "Show reset-confirmed state" })
      .click();
    await expect(state).toHaveAttribute("data-prototype-state", "available");
    await expect(page.getByText("10 seconds remaining")).toBeVisible();

    await page.getByRole("button", { name: "Undo reset" }).click();
    await expect(state).toHaveAttribute("data-prototype-state", "processing");
    await expect(
      page.getByText(
        "Review state: the undo request is processing. The previous layout is not reported as restored.",
      ),
    ).toBeVisible();

    await page.getByRole("button", { name: "Show reconciled result" }).click();
    await expect(state).toHaveAttribute("data-prototype-state", "restored");
    await expect(page.getByText("Previous personal layout")).toBeVisible();
    expect(mutationRequests).toEqual([]);
  });

  for (const undoState of controlledUndoPrototypeStates) {
    test(`opens the exact ${undoState} review state from the bounded route`, async ({
      page,
    }) => {
      await openPrototype(page, `${prototypePath}&undoState=${undoState}`, {
        locale: "en",
      });
      await expect(
        page.getByRole("region", { name: "Prototype state" }),
      ).toHaveAttribute("data-prototype-state", undoState);
      await expect(page.getByText("Prototype only")).toBeVisible();
    });
  }

  for (const locale of [
    "en",
    "zh",
    "zh-TW",
  ] as const satisfies readonly TestLocale[]) {
    test(`keeps the 1440 review surface accessible and language-pure in ${locale}`, async ({
      page,
    }, testInfo) => {
      await page.setViewportSize({ height: 900, width: 1440 });
      await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
      });
      await openPrototype(page, `${prototypePath}&undoState=available`, {
        locale,
      });
      await expect(
        page.getByRole("heading", {
          name: translate(locale, "Controlled undo review prototype"),
        }),
      ).toBeVisible();
      await expect(
        page.getByText(translate(locale, "Pending Product Owner approval")),
      ).toBeVisible();
      await expectNoMixedLanguage(page, locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      const accessibility = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(accessibility.violations).toEqual([]);
      await page.evaluate(async () => document.fonts.ready);
      await testInfo.attach(`r1-06-undo-prototype-${locale}-1440x900`, {
        body: await page.locator(".page--work").screenshot({
          animations: "disabled",
        }),
        contentType: "image/png",
      });
    });
  }
});
