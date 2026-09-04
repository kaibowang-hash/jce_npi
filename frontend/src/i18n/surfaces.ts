import type { Translator } from "./copy";
import { formatDateTime } from "./formatters";
import type { Locale } from "./runtime";

export interface OperationalSurfaceInput {
  projectCode: string;
  dueAt: string;
  generatedAt: string;
}

export interface LocalizedOperationalSurfaces {
  notification: Readonly<{ title: string; body: string }>;
  email: Readonly<{ subject: string; body: string }>;
  print: Readonly<{ title: string; generatedLabel: string }>;
  export: Readonly<{ sheetName: string; headers: readonly string[] }>;
}

export function buildLocalizedOperationalSurfaces(
  locale: Locale,
  t: Translator,
  input: OperationalSurfaceInput,
): LocalizedOperationalSurfaces {
  const dueAt = formatDateTime(locale, input.dueAt);
  const generatedAt = formatDateTime(locale, input.generatedAt);
  return {
    notification: {
      title: t("Gate review is due"),
      body: t("Project {{project}} requires a Gate review before {{dueAt}}.", {
        project: input.projectCode,
        dueAt,
      }),
    },
    email: {
      subject: t("Action required: Gate review for {{project}}", {
        project: input.projectCode,
      }),
      body: t(
        "Review the controlled evidence and complete the assigned Gate decision before {{dueAt}}.",
        { dueAt },
      ),
    },
    print: {
      title: t("Project review package"),
      generatedLabel: t("Generated {{generatedAt}}", { generatedAt }),
    },
    export: {
      sheetName: t("Work item export"),
      headers: [
        t("Item"),
        t("Project or object"),
        t("Due"),
        t("Status"),
        t("Next action"),
      ],
    },
  };
}
