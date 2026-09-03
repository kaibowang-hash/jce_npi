import { act, renderHook, waitFor } from "@testing-library/react";
import type { JSX, PropsWithChildren } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  buildFrappeLoginUrl,
  I18nProvider,
  supportedLocales,
  useI18n,
} from "../../src/i18n/runtime";
import { translate } from "../translate";
import { sessionBootstrapTimeoutMilliseconds } from "../../src/api/session";
import { buildLocalizedOperationalSurfaces } from "../../src/i18n/surfaces";

describe("Frappe-backed React localization", () => {
  it("supports only the verified language codes", () => {
    expect(supportedLocales).toEqual(["en", "zh", "zh-TW"]);
  });

  it("builds a same-site Frappe login return URL", () => {
    expect(
      buildFrappeLoginUrl({
        hash: "#review",
        pathname: "/projects/PJ-26018",
        search: "?tab=gates",
      }),
    ).toBe("/login?redirect-to=%2Fprojects%2FPJ-26018%3Ftab%3Dgates%23review");
    expect(
      buildFrappeLoginUrl({
        hash: "",
        pathname: "//untrusted.example",
        search: "",
      }),
    ).toBe("/login?redirect-to=%2F");
  });

  it("redirects an unauthenticated production bootstrap to Frappe login", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_NPI_PROTOTYPE", "false");
    globalThis.history.replaceState({}, "", "/projects/PJ-26018?tab=gates");
    const assign = vi.fn();
    vi.stubGlobal("location", {
      assign,
      hash: "",
      pathname: "/projects/PJ-26018",
      search: "?tab=gates",
    });
    const problem = {
      code: "AUTHENTICATION_REQUIRED",
      retryable: false,
      status: 401,
      title: "Authentication required",
      traceId: "trace-login-26018",
      type: "/problems/authentication-required",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(problem), {
            headers: { "X-Trace-ID": problem.traceId },
            status: 401,
          }),
        ),
      ),
    );
    const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
      <I18nProvider>{children}</I18nProvider>
    );
    const { result } = renderHook(() => useI18n(), { wrapper });

    await waitFor(() => {
      expect(assign).toHaveBeenCalledOnce();
    });
    expect(assign).toHaveBeenCalledWith(
      "/login?redirect-to=%2Fprojects%2FPJ-26018%3Ftab%3Dgates",
    );
    expect(result.current.sessionCommandContext).toBeNull();
    expect(result.current.isLocalizationUnavailable).toBe(false);
    expect(result.current.localizationFailure).toBeNull();
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

    expect(result.current.sessionCommandContext).toBeNull();
    await waitFor(() => {
      expect(result.current.isLocalizationPending).toBe(false);
    });
    expect(result.current.locale).toBe("zh-TW");
    expect(result.current.t("My Work")).toBe(translate("zh-TW", "My Work"));
    expect(document.documentElement.lang).toBe("zh-TW");
    expect(result.current.isPrototypeFallback).toBe(true);
    expect(result.current.sessionCommandContext).toBeNull();
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
    expect(result.current.sessionCommandContext).toBeNull();
    act(() => {
      result.current.setLocale("zh");
    });
    await waitFor(() => {
      expect(result.current.locale).toBe("zh");
    });
    expect(result.current.t("My Work")).toBe(translate("zh", "My Work"));
    expect(globalThis.localStorage.getItem("npi-one-prototype-locale")).toBe(
      "zh",
    );
    expect(document.documentElement.lang).toBe("zh");
    expect(result.current.sessionCommandContext).toBeNull();
  });

  it("exposes and atomically rotates the authenticated command context", async () => {
    const bootstrap = {
      allowedLanguages: supportedLocales,
      catalog: {
        language: "en" as const,
        messages: {},
        version: "a".repeat(64),
      },
      csrfToken: "bootstrap-csrf-token-fixture-123456",
      language: "en" as const,
      preferences: { navigationCollapsed: false },
      userId: "phase3@example.invalid",
    };
    const languageRefresh = {
      ...bootstrap,
      catalog: {
        ...bootstrap.catalog,
        language: "zh-TW" as const,
        version: "b".repeat(64),
      },
      csrfToken: "language-csrf-token-fixture-1234567",
      language: "zh-TW" as const,
      userId: "phase4@example.invalid",
    };
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(bootstrap), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(languageRefresh), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetch);
    const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
      <I18nProvider>{children}</I18nProvider>
    );
    const { result } = renderHook(() => useI18n(), { wrapper });

    expect(result.current.sessionCommandContext).toBeNull();
    await waitFor(() => {
      expect(result.current.sessionCommandContext).toEqual({
        csrfToken: bootstrap.csrfToken,
        userId: bootstrap.userId,
      });
    });
    expect(Object.isFrozen(result.current.sessionCommandContext)).toBe(true);
    expect(result.current.isPrototypeFallback).toBe(false);
    act(() => {
      result.current.setLocale("zh-TW");
    });
    expect(result.current.sessionCommandContext).toBeNull();
    await waitFor(() => {
      expect(result.current.sessionCommandContext).toEqual({
        csrfToken: languageRefresh.csrfToken,
        userId: languageRefresh.userId,
      });
    });
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch).toHaveBeenLastCalledWith(
      "/api/npi/v1/session/language",
      expect.objectContaining({
        body: JSON.stringify({ language: "zh-TW" }),
        method: "PUT",
      }),
    );
    const [, languageRequest] = vi.mocked(globalThis.fetch).mock.calls[1] ?? [];
    expect(
      new Headers(languageRequest?.headers).get("X-Frappe-CSRF-Token"),
    ).toBe(bootstrap.csrfToken);
    expect(result.current.locale).toBe("zh-TW");
    expect(Object.isFrozen(result.current.sessionCommandContext)).toBe(true);
  });

  it("persists navigation collapse through the authenticated session and updates only after confirmation", async () => {
    const bootstrap = {
      allowedLanguages: supportedLocales,
      catalog: {
        language: "en" as const,
        messages: {},
        version: "a".repeat(64),
      },
      csrfToken: "bootstrap-csrf-token-fixture-123456",
      language: "en" as const,
      preferences: { navigationCollapsed: false },
      userId: "phase3@example.invalid",
    };
    const confirmed = {
      ...bootstrap,
      csrfToken: "preference-csrf-token-fixture-12345",
      preferences: { navigationCollapsed: true },
    };
    let confirmPreference: ((response: Response) => void) | undefined;
    const preferenceResponse = new Promise<Response>((resolve) => {
      confirmPreference = resolve;
    });
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(bootstrap), { status: 200 }),
      )
      .mockReturnValueOnce(preferenceResponse);
    vi.stubGlobal("fetch", fetch);
    const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
      <I18nProvider>{children}</I18nProvider>
    );
    const { result } = renderHook(() => useI18n(), { wrapper });

    await waitFor(() => {
      expect(result.current.sessionCommandContext).not.toBeNull();
    });
    expect(result.current.navigationCollapsed).toBe(false);
    act(() => {
      result.current.setNavigationCollapsed(true);
    });
    expect(result.current.navigationCollapsed).toBe(false);
    expect(result.current.isNavigationPreferencePending).toBe(true);
    expect(result.current.sessionCommandContext).toBeNull();

    await act(async () => {
      confirmPreference?.(
        new Response(JSON.stringify(confirmed), { status: 200 }),
      );
      await preferenceResponse;
    });
    await waitFor(() => {
      expect(result.current.navigationCollapsed).toBe(true);
    });
    expect(result.current.isNavigationPreferencePending).toBe(false);
    expect(result.current.navigationPreferenceFailure).toBeNull();
    expect(fetch).toHaveBeenLastCalledWith(
      "/api/npi/v1/session/preferences/navigation",
      expect.objectContaining({
        body: JSON.stringify({ collapsed: true }),
        method: "PUT",
      }),
    );
    const [, preferenceRequest] =
      vi.mocked(globalThis.fetch).mock.calls[1] ?? [];
    expect(
      new Headers(preferenceRequest?.headers).get("X-Frappe-CSRF-Token"),
    ).toBe(bootstrap.csrfToken);
  });

  it("keeps the confirmed navigation mode and reconciles an indeterminate save before retrying", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_NPI_PROTOTYPE", "false");
    const bootstrap = {
      allowedLanguages: supportedLocales,
      catalog: {
        language: "en" as const,
        messages: {},
        version: "a".repeat(64),
      },
      csrfToken: "bootstrap-csrf-token-fixture-123456",
      language: "en" as const,
      preferences: { navigationCollapsed: false },
      userId: "phase3@example.invalid",
    };
    const reconciled = {
      ...bootstrap,
      csrfToken: "reconciled-csrf-token-fixture-1234",
      preferences: { navigationCollapsed: true },
    };
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(bootstrap), { status: 200 }),
      )
      .mockRejectedValueOnce(new Error("Indeterminate preference request."))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(reconciled), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetch);
    const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
      <I18nProvider>{children}</I18nProvider>
    );
    const { result } = renderHook(() => useI18n(), { wrapper });

    await waitFor(() => {
      expect(result.current.sessionCommandContext).not.toBeNull();
    });
    act(() => {
      result.current.setNavigationCollapsed(true);
    });
    await waitFor(() => {
      expect(result.current.navigationPreferenceFailure).not.toBeNull();
    });
    expect(result.current.navigationCollapsed).toBe(false);
    expect(result.current.sessionCommandContext).toBeNull();

    act(() => {
      result.current.retryNavigationPreference();
    });
    await waitFor(() => {
      expect(result.current.navigationPreferenceFailure).toBeNull();
    });
    expect(result.current.navigationCollapsed).toBe(true);
    expect(result.current.sessionCommandContext).toEqual({
      csrfToken: reconciled.csrfToken,
      userId: reconciled.userId,
    });
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(fetch.mock.calls[2]?.[0]).toBe("/api/npi/v1/session/bootstrap");
  });

  it("clears the command context when a production refresh is indeterminate", async () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_NPI_PROTOTYPE", "false");
    const bootstrap = {
      allowedLanguages: supportedLocales,
      catalog: {
        language: "en" as const,
        messages: {},
        version: "a".repeat(64),
      },
      csrfToken: "bootstrap-csrf-token-fixture-123456",
      language: "en" as const,
      preferences: { navigationCollapsed: false },
      userId: "phase3@example.invalid",
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(bootstrap), { status: 200 }),
        )
        .mockRejectedValueOnce(new Error("Indeterminate language request.")),
    );
    const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
      <I18nProvider>{children}</I18nProvider>
    );
    const { result } = renderHook(() => useI18n(), { wrapper });

    await waitFor(() => {
      expect(result.current.sessionCommandContext).not.toBeNull();
    });
    act(() => {
      result.current.setLocale("zh");
    });
    await waitFor(() => {
      expect(result.current.localizationFailure?.operation).toBe(
        "set_language",
      );
    });
    expect(result.current.sessionCommandContext).toBeNull();
    expect(result.current.isLocalizationUnavailable).toBe(true);
  });

  it("bounds a never-resolving bootstrap and uses the prototype fallback", async () => {
    vi.useFakeTimers();
    try {
      vi.stubEnv("DEV", true);
      vi.stubEnv("VITE_NPI_PROTOTYPE", "true");
      const bootstrapRequest = { signal: null as AbortSignal | null };
      const fetch = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        bootstrapRequest.signal = init?.signal ?? null;
        return new Promise<Response>(() => undefined);
      });
      vi.stubGlobal("fetch", fetch);
      const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
        <I18nProvider>{children}</I18nProvider>
      );
      const { result } = renderHook(() => useI18n(), { wrapper });

      await act(async () => {
        await Promise.resolve();
      });
      expect(fetch).toHaveBeenCalledOnce();
      expect(sessionBootstrapTimeoutMilliseconds).toBe(15_000);
      expect(result.current.isLocalizationBootstrapping).toBe(true);
      expect(bootstrapRequest.signal?.aborted).toBe(false);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(14_999);
      });
      expect(result.current.isLocalizationBootstrapping).toBe(true);
      expect(bootstrapRequest.signal?.aborted).toBe(false);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(result.current.isLocalizationBootstrapping).toBe(false);
      expect(bootstrapRequest.signal?.aborted).toBe(true);
      expect(result.current.isLocalizationPending).toBe(false);
      expect(result.current.isPrototypeFallback).toBe(true);
      expect(result.current.isLocalizationUnavailable).toBe(false);
      expect(result.current.localizationFailure).toBeNull();
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("exposes a timed-out production bootstrap and recovers through retry", async () => {
    vi.useFakeTimers();
    try {
      vi.stubEnv("DEV", false);
      vi.stubEnv("VITE_NPI_PROTOTYPE", "false");
      const bootstrap = {
        allowedLanguages: supportedLocales,
        catalog: {
          language: "en" as const,
          messages: {},
          version: "c".repeat(64),
        },
        csrfToken: "retry-csrf-token-fixture-123456789",
        language: "en" as const,
        preferences: { navigationCollapsed: false },
        userId: "recovered@example.invalid",
      };
      const fetch = vi
        .fn()
        .mockImplementationOnce(() => new Promise<Response>(() => undefined))
        .mockResolvedValueOnce(
          new Response(JSON.stringify(bootstrap), { status: 200 }),
        );
      vi.stubGlobal("fetch", fetch);
      const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
        <I18nProvider>{children}</I18nProvider>
      );
      const { result } = renderHook(() => useI18n(), { wrapper });

      await act(async () => {
        await Promise.resolve();
        await vi.advanceTimersByTimeAsync(sessionBootstrapTimeoutMilliseconds);
      });
      expect(result.current.isLocalizationPending).toBe(false);
      expect(result.current.isLocalizationUnavailable).toBe(true);
      expect(result.current.localizationFailure?.operation).toBe("bootstrap");
      expect(result.current.sessionCommandContext).toBeNull();

      await act(async () => {
        result.current.retryLocalization();
        await vi.advanceTimersByTimeAsync(0);
      });

      expect(fetch).toHaveBeenCalledTimes(2);
      expect(result.current.isLocalizationPending).toBe(false);
      expect(result.current.isLocalizationUnavailable).toBe(false);
      expect(result.current.localizationFailure).toBeNull();
      expect(result.current.isPrototypeFallback).toBe(false);
      expect(result.current.sessionCommandContext).toEqual({
        csrfToken: bootstrap.csrfToken,
        userId: bootstrap.userId,
      });
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("cancels and cleans up an in-flight bootstrap when the provider unmounts", async () => {
    vi.useFakeTimers();
    try {
      const request = { signal: null as AbortSignal | null };
      vi.stubGlobal(
        "fetch",
        vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
          request.signal = init?.signal ?? null;
          return new Promise<Response>(() => undefined);
        }),
      );
      const wrapper = ({ children }: PropsWithChildren): JSX.Element => (
        <I18nProvider>{children}</I18nProvider>
      );
      const { unmount } = renderHook(() => useI18n(), { wrapper });

      await act(async () => {
        await Promise.resolve();
      });
      expect(request.signal).not.toBeNull();
      expect(request.signal?.aborted).toBe(false);
      expect(vi.getTimerCount()).toBe(1);

      await act(async () => {
        unmount();
        await Promise.resolve();
      });

      expect(request.signal?.aborted).toBe(true);
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it.each([
    ["null messages", { messages: null }],
    ["non-string messages", { messages: { "My Work": 7 } }],
    ["invalid catalog version", { version: "not-a-catalog-version" }],
    ["invalid language set", { allowedLanguages: ["en", "zh", "zh"] }],
    [
      "invalid navigation preference",
      { preferences: { navigationCollapsed: "yes" } },
    ],
    ["short CSRF token", { csrfToken: "short" }],
    ["empty user identity", { userId: "" }],
    ["invalid administration capability", { isSystemManager: "yes" }],
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
        preferences: { navigationCollapsed: false },
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
      expect(result.current.sessionCommandContext).toBeNull();
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
