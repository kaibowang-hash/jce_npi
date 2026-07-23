import { describe, expect, it } from "vitest";

import {
  actionLabel,
  activityLabel,
  assignmentLabel,
  domainWorkItemKindLabel,
  gateLabel,
  governedPolicyLabel,
  lifecycleLabel,
  operationLabel,
  scenarioLabel,
  sourceSystemLabel,
  syncStateLabel,
  workKindLabel,
  workTitleLabel,
  type Translator,
} from "../../src/i18n/copy";
import {
  isProjectPolicyLabelSource,
  projectPolicyLabelSources,
} from "../../src/generated/project-policy-label-sources";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatList,
  formatNumber,
  formatPercent,
} from "../../src/i18n/formatters";
import { translate } from "../../src/i18n/runtime";
import {
  activities,
  executionRows,
  gateSteps,
  lifecycleSteps,
  scenarios,
  workItems,
} from "../../src/fixtures/prototype";

const identityTranslator: Translator = (source, values = {}) =>
  source.replace(
    /\{\{([A-Za-z][A-Za-z0-9_]*)\}\}/g,
    (placeholder, name: string) =>
      Object.hasOwn(values, name) ? String(values[name]) : placeholder,
  );

describe("controlled display copy", () => {
  it("translates governed policy labels and fails closed with a safe fallback", () => {
    const translatedSources: string[] = [];
    const translator: Translator = (source, values, context) => {
      translatedSources.push(source);
      return translate("zh", source, values, context);
    };

    expect(
      projectPolicyLabelSources.map((source) =>
        governedPolicyLabel(translator, source),
      ),
    ).toEqual(["草稿", "已识别", "未开始", "待处理", "已请求"]);
    expect(translatedSources).toEqual(projectPolicyLabelSources);
    translatedSources.length = 0;
    expect(governedPolicyLabel(translator, "Draft")).toBe("草稿");
    expect(translatedSources).toEqual(["Draft"]);

    const fallbackSources: string[] = [];
    const fallbackTranslator: Translator = (source) => {
      fallbackSources.push(source);
      return source;
    };
    expect(governedPolicyLabel(fallbackTranslator, "Unpublished state")).toBe(
      "Policy label unavailable",
    );
    expect(fallbackSources).toEqual(["Policy label unavailable"]);
    expect(fallbackSources).not.toContain("Unpublished state");

    expect(domainWorkItemKindLabel(translator, "action")).toBe("行动项");
  });

  it("recognizes only generated canonical Project policy label sources", () => {
    for (const source of projectPolicyLabelSources) {
      expect(isProjectPolicyLabelSource(source)).toBe(true);
    }
    expect(isProjectPolicyLabelSource("Unpublished state")).toBe(false);
    expect(isProjectPolicyLabelSource("")).toBe(false);
    expect(isProjectPolicyLabelSource(null)).toBe(false);
  });

  it("maps every stable fixture code to non-empty source copy", () => {
    for (const item of workItems) {
      expect(workKindLabel(identityTranslator, item.kind)).not.toHaveLength(0);
      expect(
        workTitleLabel(identityTranslator, item.titleCode),
      ).not.toHaveLength(0);
      expect(
        assignmentLabel(identityTranslator, item.assignmentCode),
      ).not.toHaveLength(0);
      expect(actionLabel(identityTranslator, item.actionCode)).not.toHaveLength(
        0,
      );
      expect(syncStateLabel(identityTranslator, item.status)).not.toHaveLength(
        0,
      );
      expect(
        sourceSystemLabel(identityTranslator, item.source.sourceSystem),
      ).not.toHaveLength(0);
    }
    for (const step of gateSteps)
      expect(gateLabel(identityTranslator, step)).not.toHaveLength(0);
    for (const step of lifecycleSteps)
      expect(lifecycleLabel(identityTranslator, step)).not.toHaveLength(0);
    for (const activity of activities)
      expect(activityLabel(identityTranslator, activity)).not.toHaveLength(0);
    for (const operation of executionRows) {
      expect(
        operationLabel(identityTranslator, operation.operationCode),
      ).not.toHaveLength(0);
      expect(
        syncStateLabel(identityTranslator, operation.state),
      ).not.toHaveLength(0);
    }
    for (const scenario of scenarios)
      expect(scenarioLabel(identityTranslator, scenario)).not.toHaveLength(0);
  });

  it("covers remaining source, sync, and status code branches", () => {
    for (const source of ["NPI_ONE", "ERPNEXT", "COMPUTED"] as const) {
      expect(sourceSystemLabel(identityTranslator, source)).not.toHaveLength(0);
    }
    for (const state of [
      "pending",
      "synced",
      "failed_final",
      "stale",
      "conflict",
      "queued",
      "cancelled",
      "succeeded",
    ] as const) {
      expect(syncStateLabel(identityTranslator, state)).not.toHaveLength(0);
    }
  });
});

describe("locale-aware value formatting", () => {
  const instant = "2026-07-21T14:32:00Z";

  it.each(["en", "zh", "zh-TW"] as const)(
    "matches Intl semantics for %s",
    (locale) => {
      expect(formatDate(locale, instant)).not.toHaveLength(0);
      expect(formatDateTime(locale, instant)).not.toHaveLength(0);
      expect(formatNumber(locale, 12_345.67, 2)).not.toHaveLength(0);
      expect(formatCurrency(locale, 428_000, "CNY")).not.toHaveLength(0);
      expect(formatPercent(locale, 0.62)).not.toHaveLength(0);
      expect(formatList(locale, ["A", "B", "C"])).not.toHaveLength(0);
    },
  );

  it("does not force an English presentation onto Chinese locales", () => {
    expect(formatDateTime("zh", instant)).not.toBe(
      formatDateTime("en", instant),
    );
    expect(formatDateTime("zh-TW", instant)).not.toBe(
      formatDateTime("en", instant),
    );
  });
});
