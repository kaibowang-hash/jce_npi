import { NpiHttpClient } from "./http";

export type ERPConnectionState =
  | "connected"
  | "partially_connected"
  | "not_connected"
  | "unavailable";

export interface ERPConnectionStatus {
  schemaVersion: 1;
  targetSystem: "ERPNEXT";
  targetEnvironment: "test" | null;
  connectionState: ERPConnectionState;
  lastConfirmedAt: string | null;
  capabilities: {
    authorizationSynchronization: boolean;
    itemCommands: boolean;
    projectSynchronization: boolean;
    reportingSynchronization: boolean;
  };
}

export interface ERPConnectionStatusDataSource {
  loadStatus(signal: AbortSignal): Promise<ERPConnectionStatus>;
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exact(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  return (
    Object.keys(value).length === keys.length &&
    keys.every((key) => Object.hasOwn(value, key))
  );
}

export function isERPConnectionStatus(
  value: unknown,
): value is ERPConnectionStatus {
  if (!record(value)) return false;
  const capabilities = value.capabilities;
  if (!record(capabilities)) return false;
  return (
    exact(value, [
      "schemaVersion",
      "targetSystem",
      "targetEnvironment",
      "connectionState",
      "lastConfirmedAt",
      "capabilities",
    ]) &&
    exact(capabilities, [
      "authorizationSynchronization",
      "itemCommands",
      "projectSynchronization",
      "reportingSynchronization",
    ]) &&
    value.schemaVersion === 1 &&
    value.targetSystem === "ERPNEXT" &&
    (value.targetEnvironment === "test" || value.targetEnvironment === null) &&
    [
      "connected",
      "partially_connected",
      "not_connected",
      "unavailable",
    ].includes(String(value.connectionState)) &&
    (value.lastConfirmedAt === null ||
      (typeof value.lastConfirmedAt === "string" &&
        value.lastConfirmedAt.length >= 20 &&
        value.lastConfirmedAt.length <= 40 &&
        Number.isFinite(Date.parse(value.lastConfirmedAt)))) &&
    Object.values(capabilities).every((item) => typeof item === "boolean")
  );
}

export class LiveERPConnectionStatusDataSource implements ERPConnectionStatusDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  loadStatus(signal: AbortSignal): Promise<ERPConnectionStatus> {
    return this.http.request<ERPConnectionStatus>(
      "/integration/erpnext/status",
      { signal },
      { requirePrivateNoStore: true, validate: isERPConnectionStatus },
    );
  }
}
