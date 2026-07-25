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

export function formatDateTime(
  locale: Locale,
  value: string | Date,
  timeZone = "UTC",
): string {
  return new Intl.DateTimeFormat(intlLocales[locale], {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
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

export function formatDecimal(locale: Locale, value: string): string {
  if (!/^-?[0-9]+(?:\.[0-9]+)?$/u.test(value)) {
    throw new RangeError("A canonical fixed-point decimal value is required.");
  }
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [integer = "0", fraction] = unsigned.split(".");
  const formatter = new Intl.NumberFormat(intlLocales[locale], {
    maximumFractionDigits: 0,
    useGrouping: true,
  });
  const minusSign =
    formatter.formatToParts(-1n).find((part) => part.type === "minusSign")
      ?.value ?? "-";
  const decimalSign =
    new Intl.NumberFormat(intlLocales[locale], {
      maximumFractionDigits: 1,
    })
      .formatToParts(1.1)
      .find((part) => part.type === "decimal")?.value ?? ".";
  return `${negative ? minusSign : ""}${formatter.format(BigInt(integer))}${
    fraction === undefined ? "" : `${decimalSign}${fraction}`
  }`;
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
