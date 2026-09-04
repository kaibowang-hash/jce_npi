import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";

import zhMessages from "../../src/generated/catalog-zh";
import zhTwMessages from "../../src/generated/catalog-zh-TW";
import {
  I18nProvider,
  primePrototypeMessages,
  type Locale,
} from "../../src/i18n/runtime";

primePrototypeMessages("zh", zhMessages);
primePrototypeMessages("zh-TW", zhTwMessages);

export function renderWithLocale(
  element: ReactElement,
  locale: Locale = "en",
  path = "/",
): RenderResult {
  const url = new URL(path, globalThis.location.origin);
  url.searchParams.set("lang", locale);
  globalThis.history.replaceState(
    {},
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
  return render(<I18nProvider>{element}</I18nProvider>);
}
