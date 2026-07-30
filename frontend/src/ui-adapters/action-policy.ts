export const npiIconNames = [
  "add",
  "alarm",
  "analysis",
  "apps",
  "check",
  "chevron",
  "clear",
  "collapse",
  "document",
  "error",
  "expand",
  "filter",
  "help",
  "history",
  "info",
  "keyboard",
  "maintenance",
  "play",
  "project",
  "projects",
  "refresh",
  "search",
  "upload",
  "user",
  "warning",
  "work",
] as const;

export type NpiIconName = (typeof npiIconNames)[number];

export type CompactActionIntent =
  | "ambiguous"
  | "familiar-low-risk"
  | "high-risk";

export type CompactActionProminence = "primary" | "secondary";

const npiIconNameSet: ReadonlySet<string> = new Set(npiIconNames);

export function assertNpiIconName(value: unknown): NpiIconName {
  if (typeof value !== "string" || !npiIconNameSet.has(value)) {
    throw new Error(`Unsupported local icon name: ${String(value)}`);
  }
  return value as NpiIconName;
}

export function isIconOnlyAction(
  intent: CompactActionIntent,
  prominence: CompactActionProminence,
): boolean {
  return intent === "familiar-low-risk" && prominence === "secondary";
}
