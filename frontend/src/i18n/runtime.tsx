import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { catalogs, catalogVersion } from "../generated/catalogs";
import { SessionClient, type SessionBootstrap } from "../api/session";
import { toRequestFailure, type RequestFailure } from "../api/http";

export const supportedLocales = ["en", "zh", "zh-TW"] as const;
export type Locale = (typeof supportedLocales)[number];
export type TranslationValues = Readonly<Record<string, string | number>>;

interface I18nContextValue {
  locale: Locale;
  catalogVersion: string;
  isPrototypeFallback: boolean;
  isLocalizationUnavailable: boolean;
  isLocalizationPending: boolean;
  localizationFailure: LocalizationFailure | null;
  retryLocalization: () => void;
  setLocale: (locale: Locale) => void;
  t: (source: string, values?: TranslationValues, context?: string) => string;
}

export interface LocalizationFailure {
  operation: "bootstrap" | "set_language";
  requestFailure: RequestFailure;
  requestedLocale?: Locale | undefined;
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
      "catalog",
    ]) &&
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
  const [locale, updateLocale] = useState<Locale>(resolvePrototypeLocale);
  const [runtimeCatalog, setRuntimeCatalog] = useState<
    SessionBootstrap["catalog"] | null
  >(null);
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
        updateLocale(bootstrap.language);
        setRuntimeCatalog(bootstrap.catalog);
        setPrototypeFallback(false);
        setLocalizationUnavailable(false);
        setLocalizationFailure(null);
      } catch (error) {
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
        setPendingOperation(null);
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
    [executeLocalizationRequest],
  );

  useEffect(() => {
    launchLocalizationRequest("bootstrap");
  }, [launchLocalizationRequest]);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback(
    (nextLocale: Locale): void => {
      if (pendingOperation) return;
      launchLocalizationRequest("set_language", nextLocale);
    },
    [launchLocalizationRequest, pendingOperation],
  );

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
      isPrototypeFallback,
      isLocalizationUnavailable,
      isLocalizationPending: pendingOperation !== null,
      localizationFailure,
      retryLocalization,
      setLocale,
      t: (source, values, context) =>
        translate(locale, source, values, context, runtimeCatalog?.messages),
    }),
    [
      isLocalizationUnavailable,
      isPrototypeFallback,
      locale,
      localizationFailure,
      pendingOperation,
      retryLocalization,
      runtimeCatalog,
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
