import zhMessages from "../src/generated/catalog-zh";
import zhTwMessages from "../src/generated/catalog-zh-TW";
import {
  translate as translateMessage,
  type Locale,
  type TranslationValues,
} from "../src/i18n/runtime";

const testCatalogs: Readonly<Record<Locale, Readonly<Record<string, string>>>> =
  {
    en: Object.freeze({}),
    zh: zhMessages,
    "zh-TW": zhTwMessages,
  };

export function messagesForTest(
  locale: Locale,
): Readonly<Record<string, string>> {
  return testCatalogs[locale];
}

export function translate(
  locale: Locale,
  source: string,
  values: TranslationValues = {},
  context?: string,
): string {
  return translateMessage(
    locale,
    source,
    values,
    context,
    testCatalogs[locale],
  );
}
