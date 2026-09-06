export const controlledUndoPrototypeId = "my-work-grid-reset-undo";
export const controlledUndoPrototypeRevision = "r1-06-stage-1-v1";
export const controlledUndoPrototypeDurationSeconds = 10;

export const controlledUndoPrototypeStates = [
  "review",
  "confirmation",
  "available",
  "processing",
  "restored",
  "expired",
  "conflict",
  "denied",
  "retryable",
  "final",
] as const;

export type ControlledUndoPrototypeState =
  (typeof controlledUndoPrototypeStates)[number];

const stateSet = new Set<string>(controlledUndoPrototypeStates);

export function controlledUndoPrototypeRequested(
  search = globalThis.location.search,
): boolean {
  return (
    new URLSearchParams(search).get("prototype") === controlledUndoPrototypeId
  );
}

export function controlledUndoPrototypeStateFromSearch(
  search = globalThis.location.search,
): ControlledUndoPrototypeState {
  const candidate = new URLSearchParams(search).get("undoState") ?? "";
  return stateSet.has(candidate)
    ? (candidate as ControlledUndoPrototypeState)
    : "review";
}
