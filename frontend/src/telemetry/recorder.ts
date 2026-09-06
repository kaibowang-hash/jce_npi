export type UsabilityEventName =
  | "route_viewed"
  | "action_started"
  | "action_completed"
  | "action_failed";

export interface UsabilityEvent {
  name: UsabilityEventName;
  route: string;
  outcome: "started" | "succeeded" | "failed" | "viewed";
  durationMs?: number;
  contextSwitches?: number;
  occurredAt: string;
}

const allowedKeys = new Set([
  "name",
  "route",
  "outcome",
  "durationMs",
  "contextSwitches",
  "occurredAt",
]);
const allowedNames = new Set<string>([
  "route_viewed",
  "action_started",
  "action_completed",
  "action_failed",
]);
const allowedOutcomes = new Set<string>([
  "started",
  "succeeded",
  "failed",
  "viewed",
]);
const allowedRoutes = new Set([
  "/work",
  "/project",
  "/gate",
  "/tooling",
  "/trial",
  "/execution",
]);
const utcTimestampPattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/u;

export function validateUsabilityEvent(
  event: unknown,
): asserts event is UsabilityEvent {
  if (!event || typeof event !== "object" || Array.isArray(event)) {
    throw new Error("Telemetry event must be an object.");
  }
  for (const key of Object.keys(event)) {
    if (!allowedKeys.has(key))
      throw new Error(`Sensitive telemetry field is forbidden: ${key}`);
  }
  const candidate = event as Partial<UsabilityEvent>;
  if (typeof candidate.name !== "string" || !allowedNames.has(candidate.name)) {
    throw new Error("Telemetry event name is not allowlisted.");
  }
  if (
    typeof candidate.outcome !== "string" ||
    !allowedOutcomes.has(candidate.outcome)
  ) {
    throw new Error("Telemetry outcome is not allowlisted.");
  }
  if (
    typeof candidate.route !== "string" ||
    !allowedRoutes.has(candidate.route)
  ) {
    throw new Error("Telemetry route must be a normalized screen path.");
  }
  if (
    typeof candidate.occurredAt !== "string" ||
    !utcTimestampPattern.test(candidate.occurredAt)
  ) {
    throw new Error("Telemetry timestamp must be a UTC ISO timestamp.");
  }
  const timestamp = Date.parse(candidate.occurredAt);
  const canonicalTimestamp = candidate.occurredAt.includes(".")
    ? candidate.occurredAt
    : candidate.occurredAt.replace("Z", ".000Z");
  if (
    !Number.isFinite(timestamp) ||
    new Date(timestamp).toISOString() !== canonicalTimestamp
  ) {
    throw new Error("Telemetry timestamp must be a valid UTC ISO timestamp.");
  }
  if (
    candidate.durationMs !== undefined &&
    (typeof candidate.durationMs !== "number" ||
      !Number.isFinite(candidate.durationMs) ||
      candidate.durationMs < 0)
  ) {
    throw new Error("Telemetry duration must be a finite nonnegative number.");
  }
  if (
    candidate.contextSwitches !== undefined &&
    (typeof candidate.contextSwitches !== "number" ||
      !Number.isInteger(candidate.contextSwitches) ||
      candidate.contextSwitches < 0)
  ) {
    throw new Error(
      "Telemetry context switches must be a nonnegative integer.",
    );
  }
}

export class UsabilityRecorder {
  readonly prototypeEvents: UsabilityEvent[] = [];

  async record(event: UsabilityEvent): Promise<void> {
    validateUsabilityEvent(event);
    if (import.meta.env.DEV || import.meta.env.VITE_NPI_PROTOTYPE === "true") {
      this.prototypeEvents.push(Object.freeze({ ...event }));
      return;
    }
    const response = await fetch("/api/npi/v1/telemetry", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    });
    if (!response.ok) throw new Error("Usability telemetry was not accepted.");
  }
}

export const prototypeUsabilityRecorder = new UsabilityRecorder();
