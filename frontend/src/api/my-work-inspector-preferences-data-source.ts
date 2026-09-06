import type { SessionCommandContext } from "../i18n/runtime";
import { NpiHttpClient, NpiTransportError } from "./http";

export const myWorkInspectorPaneId = "my-work-inspector" as const;
export const myWorkInspectorSchemaVersion = "my-work-inspector-v1" as const;
export const myWorkInspectorDefaultWidthPx = 340;
export const myWorkInspectorMinimumWidthPx = 260;
export const myWorkInspectorMaximumWidthPx = 480;

export interface MyWorkInspectorPreference {
  readonly collapsed: boolean;
  readonly paneId: typeof myWorkInspectorPaneId;
  readonly recoveryReason: "stored_preference_invalid" | null;
  readonly schemaVersion: typeof myWorkInspectorSchemaVersion;
  readonly widthPx: number;
}

export interface SaveMyWorkInspectorPreference {
  readonly collapsed: boolean;
  readonly schemaVersion: typeof myWorkInspectorSchemaVersion;
  readonly widthPx: number;
}

export interface MyWorkInspectorPreferencesDataSource {
  load(signal?: AbortSignal): Promise<MyWorkInspectorPreference>;
  save(
    command: SaveMyWorkInspectorPreference,
    session: SessionCommandContext,
    signal?: AbortSignal,
  ): Promise<MyWorkInspectorPreference>;
}

const endpoint = "/me/preferences/my-work-inspector";

function hasExactKeys(
  value: Readonly<Record<string, unknown>>,
  keys: readonly string[],
): boolean {
  const actual = Object.keys(value);
  return (
    actual.length === keys.length && keys.every((key) => actual.includes(key))
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isInspectorWidth(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= myWorkInspectorMinimumWidthPx &&
    value <= myWorkInspectorMaximumWidthPx
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

export function isMyWorkInspectorPreference(
  value: unknown,
): value is MyWorkInspectorPreference {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      "paneId",
      "schemaVersion",
      "widthPx",
      "collapsed",
      "recoveryReason",
    ]) &&
    value.paneId === myWorkInspectorPaneId &&
    value.schemaVersion === myWorkInspectorSchemaVersion &&
    isInspectorWidth(value.widthPx) &&
    typeof value.collapsed === "boolean" &&
    (value.recoveryReason === null ||
      value.recoveryReason === "stored_preference_invalid")
  );
}

export function isSaveMyWorkInspectorPreference(
  value: unknown,
): value is SaveMyWorkInspectorPreference {
  return (
    isRecord(value) &&
    hasExactKeys(value, ["schemaVersion", "widthPx", "collapsed"]) &&
    value.schemaVersion === myWorkInspectorSchemaVersion &&
    isInspectorWidth(value.widthPx) &&
    typeof value.collapsed === "boolean"
  );
}

export function defaultMyWorkInspectorPreference(): MyWorkInspectorPreference {
  return Object.freeze({
    collapsed: false,
    paneId: myWorkInspectorPaneId,
    recoveryReason: null,
    schemaVersion: myWorkInspectorSchemaVersion,
    widthPx: myWorkInspectorDefaultWidthPx,
  });
}

export class FrappeMyWorkInspectorPreferencesDataSource implements MyWorkInspectorPreferencesDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  load(signal?: AbortSignal): Promise<MyWorkInspectorPreference> {
    return this.http.request<MyWorkInspectorPreference>(
      endpoint,
      signal ? { signal } : {},
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isMyWorkInspectorPreference,
      },
    );
  }

  save(
    command: SaveMyWorkInspectorPreference,
    session: SessionCommandContext,
    signal?: AbortSignal,
  ): Promise<MyWorkInspectorPreference> {
    if (!isSaveMyWorkInspectorPreference(command)) {
      return Promise.reject(requestNotReady());
    }
    return this.http.request<MyWorkInspectorPreference>(
      endpoint,
      {
        body: JSON.stringify(command),
        method: "PUT",
        ...(signal ? { signal } : {}),
      },
      {
        csrfToken: session.csrfToken,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isMyWorkInspectorPreference,
      },
    );
  }
}
