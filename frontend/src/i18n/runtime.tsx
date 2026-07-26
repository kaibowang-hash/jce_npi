import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import { catalogs, catalogVersion } from "../generated/catalogs";
import { SessionClient, type SessionBootstrap } from "../api/session";
import { toRequestFailure, type RequestFailure } from "../api/http";

export const supportedLocales = ["en", "zh", "zh-TW"] as const;
export type Locale = (typeof supportedLocales)[number];
export type TranslationValues = Readonly<Record<string, string | number>>;

export interface SessionCommandContext {
  readonly userId: string;
  readonly csrfToken: string;
}

export interface I18nContextValue {
  locale: Locale;
  catalogVersion: string;
  sessionCommandContext: SessionCommandContext | null;
  navigationCollapsed: boolean;
  isNavigationPreferencePending: boolean;
  navigationPreferenceFailure: NavigationPreferenceFailure | null;
  isPrototypeFallback: boolean;
  isLocalizationBootstrapping: boolean;
  isLocalizationUnavailable: boolean;
  isLocalizationPending: boolean;
  localizationFailure: LocalizationFailure | null;
  retryNavigationPreference: () => void;
  retryLocalization: () => void;
  setNavigationCollapsed: (collapsed: boolean) => void;
  setLocale: (locale: Locale) => void;
  t: (source: string, values?: TranslationValues, context?: string) => string;
}

export interface LocalizationFailure {
  operation: "bootstrap" | "set_language";
  requestFailure: RequestFailure;
  requestedLocale?: Locale | undefined;
}

export interface NavigationPreferenceFailure {
  requestFailure: RequestFailure;
  requestedCollapsed: boolean;
}

const I18nContext = createContext<I18nContextValue | null>(null);
const prototypeStorageKey = "npi-one-prototype-locale";

function isLocale(value: string | null | undefined): value is Locale {
  return supportedLocales.some((locale) => locale === value);
}

function resolvePrototypeLocale(): Locale {
  const requested = new URLSearchParams(globalThis.location.search).get("lang");
  if (isLocale(requested)) {
    globalThis.localStorage.setItem(prototypeStorageKey, requested);
    return requested;
  }
  const stored = globalThis.localStorage.getItem(prototypeStorageKey);
  return isLocale(stored) ? stored : "en";
}

function prototypeFallbackIsAllowed(): boolean {
  return import.meta.env.DEV || import.meta.env.VITE_NPI_PROTOTYPE === "true";
}

function hasExactKeys(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  const actual = Object.keys(value);
  return (
    actual.length === keys.length && keys.every((key) => actual.includes(key))
  );
}

function isConsistentBootstrap(
  bootstrap: unknown,
  expectedLocale?: Locale,
): bootstrap is SessionBootstrap {
  if (!bootstrap || typeof bootstrap !== "object" || Array.isArray(bootstrap))
    return false;
  const candidate = bootstrap as Record<string, unknown>;
  const catalog = candidate.catalog;
  if (!catalog || typeof catalog !== "object" || Array.isArray(catalog))
    return false;
  const catalogRecord = catalog as Record<string, unknown>;
  const preferences = candidate.preferences;
  if (
    !preferences ||
    typeof preferences !== "object" ||
    Array.isArray(preferences)
  ) {
    return false;
  }
  const preferenceRecord = preferences as Record<string, unknown>;
  const messages = catalogRecord.messages;
  if (!messages || typeof messages !== "object" || Array.isArray(messages))
    return false;
  const messageRecord = messages as Record<string, unknown>;
  const allowedLanguages = candidate.allowedLanguages;
  const hasExactLanguageSet =
    Array.isArray(allowedLanguages) &&
    allowedLanguages.length === supportedLocales.length &&
    allowedLanguages.every(
      (language) => typeof language === "string" && isLocale(language),
    ) &&
    supportedLocales.every((language) => allowedLanguages.includes(language)) &&
    new Set(allowedLanguages).size === supportedLocales.length;
  return (
    hasExactKeys(candidate, [
      "userId",
      "language",
      "allowedLanguages",
      "csrfToken",
      "preferences",
      "catalog",
    ]) &&
    hasExactKeys(preferenceRecord, ["navigationCollapsed"]) &&
    typeof preferenceRecord.navigationCollapsed === "boolean" &&
    hasExactKeys(catalogRecord, ["language", "version", "messages"]) &&
    isLocale(candidate.language as string) &&
    (!expectedLocale || candidate.language === expectedLocale) &&
    hasExactLanguageSet &&
    catalogRecord.language === candidate.language &&
    typeof catalogRecord.version === "string" &&
    /^[a-f0-9]{64}$/u.test(catalogRecord.version) &&
    Object.entries(messageRecord).every(
      ([source, message]) =>
        source.length > 0 && typeof message === "string" && message.length > 0,
    ) &&
    typeof candidate.userId === "string" &&
    candidate.userId.trim().length > 0 &&
    typeof candidate.csrfToken === "string" &&
    candidate.csrfToken.length >= 32 &&
    candidate.csrfToken.length <= 128
  );
}

export function translate(
  locale: Locale,
  source: string,
  values: TranslationValues = {},
  context?: string,
  runtimeMessages?: Readonly<Record<string, string>>,
): string {
  const key = context ? `${source}:${context}` : source;
  let translated = source;
  if (locale !== "en") {
    translated =
      runtimeMessages?.[key] ??
      catalogs[locale][key as keyof (typeof catalogs)[typeof locale]];
    if (!translated) return `⟦Missing: ${source}⟧`;
  }
  return translated.replace(
    /\{\{([A-Za-z][A-Za-z0-9_]*)\}\}/g,
    (placeholder, name: string) =>
      Object.hasOwn(values, name) ? String(values[name]) : placeholder,
  );
}

export function I18nProvider({
  children,
}: PropsWithChildren): React.JSX.Element {
  const [sessionClient] = useState(() => new SessionClient());
  const providerActive = useRef(true);
  const [locale, updateLocale] = useState<Locale>(resolvePrototypeLocale);
  const [runtimeCatalog, setRuntimeCatalog] = useState<
    SessionBootstrap["catalog"] | null
  >(null);
  const [sessionCommandContext, setSessionCommandContext] =
    useState<SessionCommandContext | null>(null);
  const [navigationCollapsed, updateNavigationCollapsed] = useState(false);
  const [isNavigationPreferencePending, setNavigationPreferencePending] =
    useState(false);
  const [navigationPreferenceFailure, setNavigationPreferenceFailure] =
    useState<NavigationPreferenceFailure | null>(null);
  const [isPrototypeFallback, setPrototypeFallback] = useState(true);
  const [isLocalizationUnavailable, setLocalizationUnavailable] =
    useState(false);
  const [pendingOperation, setPendingOperation] = useState<
    LocalizationFailure["operation"] | null
  >("bootstrap");
  const [localizationFailure, setLocalizationFailure] =
    useState<LocalizationFailure | null>(null);

  const executeLocalizationRequest = useCallback(
    async (
      operation: LocalizationFailure["operation"],
      requestedLocale?: Locale,
      refreshSession = false,
    ): Promise<void> => {
      setPendingOperation(operation);
      setSessionCommandContext(null);
      try {
        let bootstrap: SessionBootstrap;
        if (operation === "bootstrap") {
          bootstrap = await sessionClient.getBootstrap((value) =>
            isConsistentBootstrap(value),
          );
        } else {
          if (!requestedLocale) {
            throw new Error(
              "A requested locale is required for this operation.",
            );
          }
          bootstrap = refreshSession
            ? await sessionClient.refreshAndSetLanguage(
                requestedLocale,
                (value) => isConsistentBootstrap(value),
                (value) => isConsistentBootstrap(value, requestedLocale),
              )
            : await sessionClient.setLanguage(requestedLocale, (value) =>
                isConsistentBootstrap(value, requestedLocale),
              );
        }
        if (!isConsistentBootstrap(bootstrap, requestedLocale)) {
          throw new Error("The session localization response is inconsistent.");
        }
        if (!providerActive.current) return;
        updateLocale(bootstrap.language);
        setRuntimeCatalog(bootstrap.catalog);
        updateNavigationCollapsed(bootstrap.preferences.navigationCollapsed);
        setSessionCommandContext(
          Object.freeze({
            userId: bootstrap.userId,
            csrfToken: bootstrap.csrfToken,
          }),
        );
        setPrototypeFallback(false);
        setLocalizationUnavailable(false);
        setLocalizationFailure(null);
        setNavigationPreferenceFailure(null);
      } catch (error) {
        if (!providerActive.current) return;
        sessionClient.clearSession();
        setSessionCommandContext(null);
        if (prototypeFallbackIsAllowed()) {
          if (operation === "set_language" && requestedLocale) {
            globalThis.localStorage.setItem(
              prototypeStorageKey,
              requestedLocale,
            );
            updateLocale(requestedLocale);
            setRuntimeCatalog(null);
          }
          setPrototypeFallback(true);
          setLocalizationUnavailable(false);
          setLocalizationFailure(null);
        } else {
          setPrototypeFallback(false);
          setLocalizationUnavailable(true);
          setLocalizationFailure({
            operation,
            requestFailure: toRequestFailure(error),
            requestedLocale,
          });
        }
      } finally {
        if (providerActive.current) setPendingOperation(null);
      }
    },
    [sessionClient],
  );

  const launchLocalizationRequest = useCallback(
    (
      operation: LocalizationFailure["operation"],
      requestedLocale?: Locale,
      refreshSession = false,
    ): void => {
      executeLocalizationRequest(
        operation,
        requestedLocale,
        refreshSession,
      ).catch((error: unknown) => {
        if (!providerActive.current) return;
        sessionClient.clearSession();
        setSessionCommandContext(null);
        setPendingOperation(null);
        setPrototypeFallback(false);
        setLocalizationUnavailable(true);
        setLocalizationFailure({
          operation,
          requestFailure: toRequestFailure(error),
          requestedLocale,
        });
      });
    },
    [executeLocalizationRequest, sessionClient],
  );

  useEffect(() => {
    let cancelled = false;
    providerActive.current = true;
    queueMicrotask(() => {
      if (!cancelled) launchLocalizationRequest("bootstrap");
    });
    return () => {
      cancelled = true;
      providerActive.current = false;
      sessionClient.cancelPendingBootstrap();
    };
  }, [launchLocalizationRequest, sessionClient]);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback(
    (nextLocale: Locale): void => {
      if (
        pendingOperation ||
        isNavigationPreferencePending ||
        navigationPreferenceFailure
      ) {
        return;
      }
      launchLocalizationRequest("set_language", nextLocale);
    },
    [
      isNavigationPreferencePending,
      launchLocalizationRequest,
      navigationPreferenceFailure,
      pendingOperation,
    ],
  );

  const executeNavigationPreferenceRequest = useCallback(
    async (collapsed: boolean, refreshSession = false): Promise<void> => {
      setNavigationPreferencePending(true);
      setSessionCommandContext(null);
      try {
        const bootstrap = refreshSession
          ? await sessionClient.refreshAndSetNavigationCollapsed(
              collapsed,
              (value) => isConsistentBootstrap(value),
              (value): value is SessionBootstrap =>
                isConsistentBootstrap(value) &&
                value.preferences.navigationCollapsed === collapsed,
            )
          : await sessionClient.setNavigationCollapsed(
              collapsed,
              (value): value is SessionBootstrap => {
                return (
                  isConsistentBootstrap(value) &&
                  value.preferences.navigationCollapsed === collapsed
                );
              },
            );
        if (
          !isConsistentBootstrap(bootstrap) ||
          bootstrap.preferences.navigationCollapsed !== collapsed
        ) {
          throw new Error(
            "The session navigation preference response is inconsistent.",
          );
        }
        if (!providerActive.current) return;
        updateLocale(bootstrap.language);
        setRuntimeCatalog(bootstrap.catalog);
        updateNavigationCollapsed(bootstrap.preferences.navigationCollapsed);
        setSessionCommandContext(
          Object.freeze({
            userId: bootstrap.userId,
            csrfToken: bootstrap.csrfToken,
          }),
        );
        setPrototypeFallback(false);
        setLocalizationUnavailable(false);
        setLocalizationFailure(null);
        setNavigationPreferenceFailure(null);
      } catch (error) {
        if (!providerActive.current) return;
        sessionClient.clearSession();
        setSessionCommandContext(null);
        setNavigationPreferenceFailure({
          requestFailure: toRequestFailure(error),
          requestedCollapsed: collapsed,
        });
      } finally {
        if (providerActive.current) setNavigationPreferencePending(false);
      }
    },
    [sessionClient],
  );

  const setNavigationCollapsed = useCallback(
    (collapsed: boolean): void => {
      if (
        pendingOperation ||
        isNavigationPreferencePending ||
        navigationPreferenceFailure
      ) {
        return;
      }
      if (isPrototypeFallback) {
        updateNavigationCollapsed(collapsed);
        return;
      }
      void executeNavigationPreferenceRequest(collapsed);
    },
    [
      executeNavigationPreferenceRequest,
      isNavigationPreferencePending,
      isPrototypeFallback,
      navigationPreferenceFailure,
      pendingOperation,
    ],
  );

  const retryNavigationPreference = useCallback((): void => {
    if (!navigationPreferenceFailure || isNavigationPreferencePending) return;
    void executeNavigationPreferenceRequest(
      navigationPreferenceFailure.requestedCollapsed,
      true,
    );
  }, [
    executeNavigationPreferenceRequest,
    isNavigationPreferencePending,
    navigationPreferenceFailure,
  ]);

  const retryLocalization = useCallback((): void => {
    if (!localizationFailure || pendingOperation) return;
    launchLocalizationRequest(
      localizationFailure.operation,
      localizationFailure.requestedLocale,
      localizationFailure.operation === "set_language",
    );
  }, [launchLocalizationRequest, localizationFailure, pendingOperation]);

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      catalogVersion: runtimeCatalog?.version ?? catalogVersion,
      sessionCommandContext,
      navigationCollapsed,
      isNavigationPreferencePending,
      navigationPreferenceFailure,
      isPrototypeFallback,
      isLocalizationBootstrapping: pendingOperation === "bootstrap",
      isLocalizationUnavailable,
      isLocalizationPending: pendingOperation !== null,
      localizationFailure,
      retryNavigationPreference,
      retryLocalization,
      setNavigationCollapsed,
      setLocale,
      t: (source, values, context) =>
        translate(locale, source, values, context, runtimeCatalog?.messages),
    }),
    [
      isLocalizationUnavailable,
      isNavigationPreferencePending,
      isPrototypeFallback,
      locale,
      localizationFailure,
      navigationCollapsed,
      navigationPreferenceFailure,
      pendingOperation,
      retryNavigationPreference,
      retryLocalization,
      runtimeCatalog,
      sessionCommandContext,
      setNavigationCollapsed,
      setLocale,
    ],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("I18nProvider is required.");
  return value;
}
