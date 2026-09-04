import { describe, expect, it, vi } from "vitest";

import {
  FrappeMyWorkGridPreferencesDataSource,
  defaultMyWorkGridFilter,
  defaultMyWorkGridLayout,
  defaultMyWorkGridPreferences,
  isMyWorkGridFilter,
  isMyWorkGridLayout,
  isMyWorkGridPreferences,
  myWorkTableSchemaVersion,
  truncateMyWorkGridSearch,
  type MyWorkGridPreferences,
  type SaveMyWorkGridPreference,
} from "../../src/api/grid-preferences-data-source";
import { NpiHttpClient } from "../../src/api/http";

function clonePreferences(): MyWorkGridPreferences {
  return structuredClone(defaultMyWorkGridPreferences());
}

describe("My Work grid preference contract", () => {
  it("accepts only the complete fixed grid, schema, views, columns, and denied capabilities", () => {
    const value = clonePreferences();
    expect(isMyWorkGridPreferences(value)).toBe(true);

    expect(
      isMyWorkGridPreferences({
        ...value,
        userId: "another-user@example.invalid",
      }),
    ).toBe(false);
    expect(
      isMyWorkGridPreferences({
        ...value,
        capabilities: {
          ...value.capabilities,
          canPublishSharedView: true,
        },
      }),
    ).toBe(false);
    expect(
      isMyWorkGridPreferences({
        ...value,
        viewLayouts: [...value.viewLayouts].reverse(),
      }),
    ).toBe(false);
    expect(
      isMyWorkGridPreferences({
        ...value,
        recoveryReason: "stored_preference_invalid",
      }),
    ).toBe(true);
    expect(
      isMyWorkGridPreferences({
        ...value,
        recoveryReason: "unknown_recovery",
      }),
    ).toBe(false);
  });

  it("rejects unknown, duplicate, hidden-required, and out-of-range layout values", () => {
    const layout = defaultMyWorkGridLayout();
    expect(isMyWorkGridLayout(layout)).toBe(true);
    expect(
      isMyWorkGridLayout({
        ...layout,
        widths: { ...layout.widths, item: 179 },
      }),
    ).toBe(false);
    expect(
      isMyWorkGridLayout({
        ...layout,
        hiddenColumnIds: ["item"],
      }),
    ).toBe(false);
    expect(
      isMyWorkGridLayout({
        ...layout,
        columnOrder: [
          "type",
          "item",
          "context",
          "assignment",
          "priority",
          "due",
          "status",
          "status",
        ],
      }),
    ).toBe(false);
    expect(
      isMyWorkGridLayout({
        ...layout,
        fixedColumnCount: 3,
      }),
    ).toBe(false);
  });

  it("validates bounded filter snapshots without accepting arbitrary expressions", () => {
    const filter = defaultMyWorkGridFilter();
    expect(isMyWorkGridFilter(filter)).toBe(true);
    expect(
      isMyWorkGridFilter({
        ...filter,
        projectId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        priority: { scheme: "domain_severity", value: "critical" },
        search: "hot runner",
      }),
    ).toBe(true);
    expect(
      isMyWorkGridFilter({
        ...filter,
        projectId: "aaaaaaaa-aaaa-0000-0000-aaaaaaaaaaaa",
      }),
    ).toBe(true);
    expect(
      isMyWorkGridFilter({
        ...filter,
        projectId: "00000000-0000-0000-0000-000000000000",
      }),
    ).toBe(false);
    expect(
      isMyWorkGridFilter({
        ...filter,
        expression: "status = 'ready'",
      }),
    ).toBe(false);
    expect(
      isMyWorkGridFilter({
        ...filter,
        priority: { scheme: "domain_severity", value: "urgent" },
      }),
    ).toBe(false);
    expect(
      isMyWorkGridFilter({
        ...filter,
        search: ` ${"a".repeat(140)}`,
      }),
    ).toBe(false);
    const maximumSupplementarySearch = "😀".repeat(140);
    expect(
      isMyWorkGridFilter({
        ...filter,
        search: maximumSupplementarySearch,
      }),
    ).toBe(true);
    expect(
      isMyWorkGridFilter({
        ...filter,
        search: `${maximumSupplementarySearch}😀`,
      }),
    ).toBe(false);
    expect(truncateMyWorkGridSearch(`${maximumSupplementarySearch}😀`)).toBe(
      maximumSupplementarySearch,
    );
  });
});

describe("FrappeMyWorkGridPreferencesDataSource", () => {
  it("loads only the fixed current-actor resource with private response validation", async () => {
    const response = clonePreferences();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(response as T));
    const source = new FrappeMyWorkGridPreferencesDataSource(http);
    const controller = new AbortController();

    await expect(source.load(controller.signal)).resolves.toEqual(response);
    expect(request).toHaveBeenCalledWith(
      "/me/preferences/my-work-grid",
      { signal: controller.signal },
      expect.objectContaining({
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isMyWorkGridPreferences,
      }),
    );
  });

  it("saves the exact versioned view payload with session CSRF and no caller identity or key", async () => {
    const response = clonePreferences();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(response as T));
    const source = new FrappeMyWorkGridPreferencesDataSource(http);
    const command: SaveMyWorkGridPreference = {
      defaultProjectId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      expectedVersion: 4,
      favoriteViewIds: ["overdue"],
      filter: {
        priority: { scheme: "domain_severity", value: "high" },
        projectId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        search: "runner",
      },
      layout: defaultMyWorkGridLayout(),
      recentViewIds: ["overdue", "all"],
      saveFilter: true,
      tableSchemaVersion: myWorkTableSchemaVersion,
      viewId: "overdue",
    };

    await expect(
      source.save(command, {
        csrfToken: "c".repeat(32),
        userId: "manager@example.invalid",
      }),
    ).resolves.toEqual(response);

    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe("/me/preferences/my-work-grid");
    expect(init).toMatchObject({ method: "PUT" });
    const body = init?.body;
    expect(typeof body).toBe("string");
    if (typeof body !== "string") {
      throw new TypeError("Expected a serialized grid preference body.");
    }
    const parsed: unknown = JSON.parse(body);
    expect(parsed).toEqual(command);
    expect(Object.keys(parsed as Record<string, unknown>).sort()).toEqual(
      [
        "defaultProjectId",
        "expectedVersion",
        "favoriteViewIds",
        "filter",
        "layout",
        "recentViewIds",
        "saveFilter",
        "tableSchemaVersion",
        "viewId",
      ].sort(),
    );
    expect(JSON.stringify(parsed)).not.toContain("manager@example.invalid");
    expect(JSON.stringify(parsed)).not.toContain("preferenceKey");
    expect(options).toMatchObject({
      csrfToken: "c".repeat(32),
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
      validate: isMyWorkGridPreferences,
    });
  });
});
