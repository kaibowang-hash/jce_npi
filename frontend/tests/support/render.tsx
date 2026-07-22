import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";

import { I18nProvider, type Locale } from "../../src/i18n/runtime";

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
