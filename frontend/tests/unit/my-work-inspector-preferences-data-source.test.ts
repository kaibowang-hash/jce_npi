import { describe, expect, it, vi } from "vitest";

import {
  FrappeMyWorkInspectorPreferencesDataSource,
  defaultMyWorkInspectorPreference,
  isMyWorkInspectorPreference,
  isSaveMyWorkInspectorPreference,
  myWorkInspectorMaximumWidthPx,
  myWorkInspectorMinimumWidthPx,
  myWorkInspectorPaneId,
  myWorkInspectorSchemaVersion,
  type MyWorkInspectorPreference,
  type SaveMyWorkInspectorPreference,
} from "../../src/api/my-work-inspector-preferences-data-source";
import { NpiHttpClient } from "../../src/api/http";
import type { SessionCommandContext } from "../../src/i18n/runtime";

const session: SessionCommandContext = {
  csrfToken: "authenticated-inspector-csrf-fixture",
  userId: "engineer@example.invalid",
};

function preferenceFixture(
  overrides: Partial<MyWorkInspectorPreference> = {},
): MyWorkInspectorPreference {
  return {
    ...defaultMyWorkInspectorPreference(),
    ...overrides,
  };
}

describe("My Work inspector preference contract", () => {
  it("accepts only the exact fixed response shape and bounded integer width", () => {
    expect(isMyWorkInspectorPreference(preferenceFixture())).toBe(true);
    expect(
      isMyWorkInspectorPreference(
        preferenceFixture({
          recoveryReason: "stored_preference_invalid",
        }),
      ),
    ).toBe(true);

    for (const invalid of [
      { ...preferenceFixture(), actor: "another-user@example.invalid" },
      { ...preferenceFixture(), paneId: "another-pane" },
      { ...preferenceFixture(), schemaVersion: "my-work-inspector-v2" },
      {
        ...preferenceFixture(),
        widthPx: myWorkInspectorMinimumWidthPx - 1,
      },
      {
        ...preferenceFixture(),
        widthPx: myWorkInspectorMaximumWidthPx + 1,
      },
      { ...preferenceFixture(), widthPx: 340.5 },
      { ...preferenceFixture(), collapsed: "false" },
      { ...preferenceFixture(), recoveryReason: "unknown_recovery" },
    ]) {
      expect(isMyWorkInspectorPreference(invalid)).toBe(false);
    }
  });

  it("accepts only the exact PUT request without an actor, pane key, or recovery field", () => {
    const command: SaveMyWorkInspectorPreference = {
      collapsed: true,
      schemaVersion: myWorkInspectorSchemaVersion,
      widthPx: 420,
    };
    expect(isSaveMyWorkInspectorPreference(command)).toBe(true);
    expect(
      isSaveMyWorkInspectorPreference({
        ...command,
        paneId: myWorkInspectorPaneId,
      }),
    ).toBe(false);
    expect(
      isSaveMyWorkInspectorPreference({
        ...command,
        userId: session.userId,
      }),
    ).toBe(false);
    expect(
      isSaveMyWorkInspectorPreference({
        ...command,
        widthPx: myWorkInspectorMaximumWidthPx + 1,
      }),
    ).toBe(false);
    expect(
      isSaveMyWorkInspectorPreference({
        ...command,
        widthPx: 400.25,
      }),
    ).toBe(false);
  });
});

describe("FrappeMyWorkInspectorPreferencesDataSource", () => {
  it("loads the fixed current-actor resource with strict private response validation", async () => {
    const response = preferenceFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(response as T));
    const source = new FrappeMyWorkInspectorPreferencesDataSource(http);
    const controller = new AbortController();

    await expect(source.load(controller.signal)).resolves.toEqual(response);
    expect(request).toHaveBeenCalledWith(
      "/me/preferences/my-work-inspector",
      { signal: controller.signal },
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isMyWorkInspectorPreference,
      },
    );
  });

  it("sends the exact versioned PUT body with the active session CSRF token", async () => {
    const response = preferenceFixture({ collapsed: true, widthPx: 380 });
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string | URL | Request, init?: RequestInit) => {
        const requestHeaders = new Headers(init?.headers);
        const requestId = requestHeaders.get("X-Request-ID");
        if (!requestId) throw new Error("The request ID is required.");
        return Promise.resolve(
          new Response(JSON.stringify(response), {
            headers: {
              "Cache-Control": "private, no-store",
              "X-Request-ID": requestId,
              "X-Trace-ID": "trace-inspector-preference",
            },
            status: 200,
          }),
        );
      }),
    );
    const command: SaveMyWorkInspectorPreference = {
      collapsed: true,
      schemaVersion: myWorkInspectorSchemaVersion,
      widthPx: 380,
    };

    await expect(
      new FrappeMyWorkInspectorPreferencesDataSource().save(command, session),
    ).resolves.toEqual(response);

    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0] ?? [];
    expect(url).toBe("/api/npi/v1/me/preferences/my-work-inspector");
    expect(init?.method).toBe("PUT");
    expect(init?.credentials).toBe("same-origin");
    const headers = new Headers(init?.headers);
    expect(headers.get("Accept")).toBe(
      "application/json, application/problem+json",
    );
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-Frappe-CSRF-Token")).toBe(session.csrfToken);
    const body = init?.body;
    expect(typeof body).toBe("string");
    if (typeof body !== "string") {
      throw new TypeError("Expected a serialized inspector preference body.");
    }
    expect(JSON.parse(body)).toEqual(command);
    expect(body).not.toContain(session.userId);
    expect(Object.keys(command).sort()).toEqual(
      ["collapsed", "schemaVersion", "widthPx"].sort(),
    );
  });

  it("rejects a malformed command before transport", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new FrappeMyWorkInspectorPreferencesDataSource(http);
    const invalid = {
      collapsed: false,
      schemaVersion: myWorkInspectorSchemaVersion,
      widthPx: myWorkInspectorMinimumWidthPx - 1,
    } as SaveMyWorkInspectorPreference;

    await expect(source.save(invalid, session)).rejects.toMatchObject({
      kind: "request_not_ready",
      referenceKind: "client",
    });
    expect(request).not.toHaveBeenCalled();
  });
});
