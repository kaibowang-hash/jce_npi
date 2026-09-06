import { readFileSync } from "node:fs";
import { catalogFromRows, parseCsv } from "../scripts/shared.mjs";
import type { Locale } from "../src/i18n/runtime";

// Test API responses model Frappe's full server catalog, independently of the
// browser's literal React subset. Missing server messages fail the fixture.
const catalogs = Object.fromEntries(
  (["zh", "zh-TW"] as const).map((locale) => {
    const file = new URL(
      `../../apps/npi_core/npi_core/translations/${locale}.csv`,
      import.meta.url,
    );
    return [
      locale,
      catalogFromRows(
        parseCsv(readFileSync(file, "utf8"), file.pathname),
        file.pathname,
      ),
    ];
  }),
);
export function translateServerMessage(locale: Locale, source: string): string {
  if (locale === "en") return source;
  const value = catalogs[locale]?.get(source);
  if (!value)
    throw new Error(`Missing Frappe server fixture message: ${source}`);
  return value;
}
