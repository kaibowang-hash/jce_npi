import { act, renderHook, waitFor } from "@testing-library/react";
import type { JSX, PropsWithChildren } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  I18nProvider,
  supportedLocales,
  translate,
  useI18n,
} from "../../src/i18n/runtime";
import { buildLocalizedOperationalSurfaces } from "../../src/i18n/surfaces";

describe("Frappe-backed React localization", () => {
  it("supports only the verified language codes", () => {
    expect(supportedLocales).toEqual(["en", "zh", "zh-TW"]);
  });

  it("translates both Chinese catalogs and substitutes named placeholders", () => {
    expect(translate("en", "{{count}} notifications", { count: 3 })).toBe(
      "3 notifications",
    );
    expect(translate("zh", "My Work")).not.toBe("My Work");
    expect(translate("zh-TW", "My Work")).not.toBe("My Work");
    expect(translate("zh", "Catalog")).toBe("目录");
    expect(translate("zh-TW", "Object page sections", {}, "aria-label")).toBe(
      "工程物件頁分區",
    );
  });

  it("makes a missing direct translation conspicuous", () => {
    expect(translate("zh-TW", "Source that is intentionally absent")).toBe(
      "⟦Missing: Source that is intentionally absent⟧",
    );
  });

  it.each(supportedLocales)(
    "renders notification, email, print, and export surfaces from the shared %s catalog",
    (locale) => {
      const surfaces = buildLocalizedOperationalSurfaces(
        locale,
        (source, values, context) => translate(locale, source, values, context),
        {
          projectCode: "PJ-26018",
          dueAt: "2026-07-21T16:00:00Z",
          generatedAt: "2026-07-21T14:32:00Z",
        },
      );
      const rendered = JSON.stringify(surfaces);

      expect(rendered).toContain("PJ-26018");
      expect(rendered).not.toContain("⟦Missing:");
      expect(surfaces.export.headers).toHaveLength(5);
      if (locale !== "en") {
        expect(rendered).not.toContain("Gate review is due");
        expect(rendered).not.toContain("Project review package");
        expect(rendered).not.toContain("Work item export");
      }
    },
  );

  it("takes the initial prototype locale from the URL and updates the document language", async () => {
    globalThis.history.replaceState({}, "", "/work?lang=zh-TW");
    const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
      <I18nProvider>{children}</I18nProvider>
    );
    const { result } = renderHook(() => useI18n(), { wrapper });

    await waitFor(() => {
      expect(result.current.locale).toBe("zh-TW");
    });
    expect(document.documentElement.lang).toBe("zh-TW");
    expect(result.current.isPrototypeFallback).toBe(true);
  });

  it("persists a development fallback preference when the controlled API is unavailable", async () => {
    globalThis.history.replaceState({}, "", "/work?lang=en");
    const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
      <I18nProvider>{children}</I18nProvider>
    );
    const { result } = renderHook(() => useI18n(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLocalizationPending).toBe(false);
    });
    act(() => {
      result.current.setLocale("zh");
    });
    await waitFor(() => {
      expect(result.current.locale).toBe("zh");
    });
    expect(globalThis.localStorage.getItem("npi-one-prototype-locale")).toBe(
      "zh",
    );
    expect(document.documentElement.lang).toBe("zh");
  });

  it("uses the authenticated Frappe session response when available", async () => {
    const bootstrap = {
      allowedLanguages: supportedLocales,
      catalog: {
        language: "zh" as const,
        messages: {},
        version: "a".repeat(64),
      },
      csrfToken: "csrf-token-fixture-value-1234567890",
      language: "zh" as const,
      userId: "phase3@example.invalid",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(bootstrap), { status: 200 }),
        ),
      ),
    );
    const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
      <I18nProvider>{children}</I18nProvider>
    );
    const { result } = renderHook(() => useI18n(), { wrapper });

    await waitFor(() => {
      expect(result.current.locale).toBe("zh");
    });
    expect(result.current.isPrototypeFallback).toBe(false);
    act(() => {
      result.current.setLocale("zh-TW");
    });
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledTimes(2);
    });
    expect(globalThis.fetch).toHaveBeenLastCalledWith(
      "/api/npi/v1/session/language",
      expect.objectContaining({
        body: JSON.stringify({ language: "zh-TW" }),
        method: "PUT",
      }),
    );
  });

  it.each([
    ["null messages", { messages: null }],
    ["non-string messages", { messages: { "My Work": 7 } }],
    ["invalid catalog version", { version: "not-a-catalog-version" }],
    ["invalid language set", { allowedLanguages: ["en", "zh", "zh"] }],
    ["short CSRF token", { csrfToken: "short" }],
    ["empty user identity", { userId: "" }],
  ])(
    "rejects a malformed successful bootstrap with %s",
    async (_name, change) => {
      vi.stubEnv("DEV", false);
      vi.stubEnv("VITE_NPI_PROTOTYPE", "false");
      const valid = {
        allowedLanguages: supportedLocales,
        catalog: {
          language: "en",
          messages: {},
          version: "a".repeat(64),
        },
        csrfToken: "a".repeat(32),
        language: "en",
        userId: "phase3@example.invalid",
      };
      const changeRecord = change as Record<string, unknown>;
      const topLevelChange = Object.fromEntries(
        Object.entries(changeRecord).filter(
          ([key]) => key !== "messages" && key !== "version",
        ),
      );
      const malformed = {
        ...valid,
        ...topLevelChange,
        catalog: {
          ...valid.catalog,
          ...(Object.hasOwn(changeRecord, "messages")
            ? { messages: changeRecord.messages }
            : {}),
          ...(Object.hasOwn(changeRecord, "version")
            ? { version: changeRecord.version }
            : {}),
        },
      };
      vi.stubGlobal(
        "fetch",
        vi.fn(() =>
          Promise.resolve(
            new Response(JSON.stringify(malformed), { status: 200 }),
          ),
        ),
      );
      const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
        <I18nProvider>{children}</I18nProvider>
      );
      const { result } = renderHook(() => useI18n(), { wrapper });

      await waitFor(() => {
        expect(result.current.localizationFailure).not.toBeNull();
      });
      expect(result.current.locale).toBe("en");
      expect(result.current.t("My Work")).toBe("My Work");
      expect(
        result.current.localizationFailure?.requestFailure.referenceKind,
      ).toBe("request");
    },
  );

  it("requires the provider boundary", () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    expect(() => renderHook(() => useI18n())).toThrow(
      "I18nProvider is required.",
    );
    expect(consoleError).toHaveBeenCalled();
  });
});
