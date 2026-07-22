import type { Locale } from "./runtime";

const intlLocales: Record<Locale, string> = {
  en: "en-US",
  zh: "zh-CN",
  "zh-TW": "zh-TW",
};

export function formatDate(locale: Locale, value: string | Date): string {
  return new Intl.DateTimeFormat(intlLocales[locale], {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function formatDateTime(locale: Locale, value: string | Date): string {
  return new Intl.DateTimeFormat(intlLocales[locale], {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function formatNumber(
  locale: Locale,
  value: number,
  maximumFractionDigits = 1,
): string {
  return new Intl.NumberFormat(intlLocales[locale], {
    maximumFractionDigits,
  }).format(value);
}

export function formatCurrency(
  locale: Locale,
  value: number,
  currency: string,
): string {
  return new Intl.NumberFormat(intlLocales[locale], {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(locale: Locale, value: number): string {
  return new Intl.NumberFormat(intlLocales[locale], {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatList(locale: Locale, values: readonly string[]): string {
  return new Intl.ListFormat(intlLocales[locale], {
    style: "long",
    type: "conjunction",
  }).format(values);
}
