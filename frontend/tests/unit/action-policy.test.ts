import { describe, expect, it } from "vitest";

import {
  assertNpiIconName,
  isIconOnlyAction,
  npiIconNames,
} from "../../src/ui-adapters/action-policy";

describe("local icon action policy", () => {
  it("keeps the bounded R1-05 action icons in the local catalog", () => {
    expect(npiIconNames).toEqual(
      expect.arrayContaining([
        "clear",
        "collapse",
        "expand",
        "refresh",
        "upload",
      ]),
    );
    for (const iconName of npiIconNames) {
      expect(assertNpiIconName(iconName)).toBe(iconName);
    }
  });

  it("fails closed for unknown or vendor-specific icon names", () => {
    expect(() => assertNpiIconName("octicon-trash")).toThrow(
      "Unsupported local icon name: octicon-trash",
    );
    expect(() => assertNpiIconName(null)).toThrow(
      "Unsupported local icon name: null",
    );
  });

  it("permits icon-only rendering only for familiar low-risk secondary actions", () => {
    expect(isIconOnlyAction("familiar-low-risk", "secondary")).toBe(true);
    expect(isIconOnlyAction("familiar-low-risk", "primary")).toBe(false);
    expect(isIconOnlyAction("ambiguous", "secondary")).toBe(false);
    expect(isIconOnlyAction("high-risk", "secondary")).toBe(false);
  });
});
