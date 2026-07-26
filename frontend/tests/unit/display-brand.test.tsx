import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  applyDisplayBrandDocument,
  DisplayBrandBootstrap,
  DisplayBrandCompanyMark,
  DisplayBrandPlatformIcon,
  displayBrandAssets,
  DisplayBrandWordmark,
} from "../../src/ui-adapters/display-brand";
import { I18nProvider } from "../../src/i18n/runtime";

describe("LaunchFlow display-brand adapter", () => {
  it("maps every approved context to the exact sole-source filename", () => {
    expect(
      Object.fromEntries(
        Object.entries(displayBrandAssets).map(([context, asset]) => [
          context,
          asset.documentName,
        ]),
      ),
    ).toEqual({
      "company-footer": "Company LOGO.svg",
      "entry-loading": "Loading.svg",
      favicon: "LaunchFlow Icon.svg",
      "platform-source": "LaunchFlow Icon.svg",
      "wordmark-dark": "LaunchFlow-logo_White.svg",
      "wordmark-light": "LaunchFlow-logo_Standard.svg",
    });
    expect(displayBrandAssets.favicon).toBe(
      displayBrandAssets["platform-source"],
    );
    expect(
      new Set(Object.values(displayBrandAssets).map((asset) => asset.url)).size,
    ).toBe(5);
    for (const asset of Object.values(displayBrandAssets)) {
      expect(asset.url).not.toMatch(/^data:/u);
    }
  });

  it("renders the approved dark, light, source, and footer contexts", () => {
    render(
      <>
        <DisplayBrandWordmark accessibleName="LaunchFlow" surface="dark" />
        <DisplayBrandWordmark
          accessibleName="LaunchFlow light"
          surface="light"
        />
        <DisplayBrandPlatformIcon accessibleName="LaunchFlow platform" />
        <DisplayBrandCompanyMark accessibleName="Company ownership mark" />
      </>,
    );

    expect(screen.getByRole("img", { name: "LaunchFlow" })).toHaveAttribute(
      "data-brand-context",
      "wordmark-dark",
    );
    expect(
      screen.getByRole("img", { name: "LaunchFlow light" }),
    ).toHaveAttribute("data-brand-context", "wordmark-light");
    expect(
      screen.getByRole("img", { name: "LaunchFlow platform" }),
    ).toHaveAttribute("data-brand-context", "platform-source");
    expect(
      screen.getByRole("img", { name: "LaunchFlow platform" }),
    ).toHaveAttribute("tabindex", "0");
    expect(
      screen.getByRole("img", { name: "LaunchFlow platform" }),
    ).toHaveAttribute(
      "aria-describedby",
      screen.getByRole("tooltip").getAttribute("id"),
    );
    expect(screen.getByRole("tooltip")).toHaveTextContent(
      "LaunchFlow platform",
    );
    expect(
      screen.getByRole("img", { name: "Company ownership mark" }),
    ).toHaveAttribute("data-brand-context", "company-footer");
  });

  it("sets the LaunchFlow title and exact icon favicon without duplicating links", () => {
    document.head.innerHTML = `
      <link
        rel="icon"
        type="image/svg+xml"
        href="/entry-favicon.svg"
        data-brand-asset="LaunchFlow Icon.svg"
        data-brand-context="favicon"
      />
    `;

    const first = applyDisplayBrandDocument(document, "LaunchFlow");
    const second = applyDisplayBrandDocument(document, "LaunchFlow");

    expect(document.title).toBe("LaunchFlow");
    expect(second).toBe(first);
    expect(document.head.querySelectorAll('link[rel~="icon"]')).toHaveLength(1);
    expect(first).toHaveAttribute("type", "image/svg+xml");
    expect(first).toHaveAttribute("data-brand-asset", "LaunchFlow Icon.svg");
    expect(first).toHaveAttribute("data-brand-context", "favicon");
  });

  it("uses Loading.svg only for the translated pre-Shell bootstrap surface", async () => {
    let rejectBootstrap: ((reason?: unknown) => void) | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((_resolve, reject) => {
            rejectBootstrap = reject;
          }),
      ),
    );
    globalThis.history.replaceState({}, "", "/?lang=zh-TW");

    render(
      <I18nProvider>
        <DisplayBrandBootstrap>
          <p>Ready fixture</p>
        </DisplayBrandBootstrap>
      </I18nProvider>,
    );

    const loading = screen.getByRole("status", {
      name: "正在載入 LaunchFlow",
    });
    expect(loading).toHaveAttribute("aria-busy", "true");
    expect(loading.querySelector("img")).toHaveAttribute(
      "data-brand-context",
      "entry-loading",
    );
    expect(loading).toHaveTextContent("正在載入 LaunchFlow");

    await waitFor(() => {
      expect(rejectBootstrap).toBeDefined();
    });
    rejectBootstrap?.(new Error("No Frappe Site fixture."));
    await waitFor(() => {
      expect(screen.getByText("Ready fixture")).toBeVisible();
    });
    expect(
      document.querySelector('[data-brand-context="entry-loading"]'),
    ).toBeNull();
  });
});
