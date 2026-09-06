export interface WorkspaceDirtyRegistration {
  objectIdentity: string;
  version: string;
  returnFocusTarget: () => HTMLElement | null;
}

export type ReportWorkspaceDirty = (
  registration: WorkspaceDirtyRegistration | null,
) => void;

export type RequestWorkspaceTransition = (
  perform: () => void,
  returnFocusTarget?: HTMLElement | null,
) => void;
