import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  FrappeMyWorkInspectorPreferencesDataSource,
  defaultMyWorkInspectorPreference,
  isSaveMyWorkInspectorPreference,
  myWorkInspectorSchemaVersion,
  type MyWorkInspectorPreference,
  type MyWorkInspectorPreferencesDataSource,
  type SaveMyWorkInspectorPreference,
} from "../api/my-work-inspector-preferences-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { SessionCommandContext } from "../i18n/runtime";

export type MyWorkInspectorPreferenceStatus =
  | "failed"
  | "loading"
  | "ready"
  | "saving"
  | "unavailable";

export interface UpdateMyWorkInspectorPreference {
  readonly collapsed: boolean;
  readonly widthPx: number;
}

export interface MyWorkInspectorPersonalizationController {
  readonly canUpdate: boolean;
  readonly failure: RequestFailure | null;
  readonly preference: MyWorkInspectorPreference;
  readonly reload: () => void;
  readonly status: MyWorkInspectorPreferenceStatus;
  readonly update: (next: UpdateMyWorkInspectorPreference) => void;
}

interface PendingPreference {
  readonly command: SaveMyWorkInspectorPreference;
}

interface ActiveSessionRequest {
  readonly controller: AbortController;
  readonly generation: number;
  readonly identity: string;
  readonly session: SessionCommandContext;
}

export function useMyWorkInspectorPersonalization({
  dataSource: suppliedDataSource,
  session,
}: {
  readonly dataSource?: MyWorkInspectorPreferencesDataSource;
  readonly session: SessionCommandContext | null;
}): MyWorkInspectorPersonalizationController {
  const dataSource = useMemo(
    () =>
      suppliedDataSource ?? new FrappeMyWorkInspectorPreferencesDataSource(),
    [suppliedDataSource],
  );
  const initial = useMemo(() => defaultMyWorkInspectorPreference(), []);
  const sessionUserId = session?.userId;
  const sessionCsrfToken = session?.csrfToken;
  const sessionSnapshot = useMemo<SessionCommandContext | null>(
    () =>
      sessionUserId === undefined || sessionCsrfToken === undefined
        ? null
        : { csrfToken: sessionCsrfToken, userId: sessionUserId },
    [sessionCsrfToken, sessionUserId],
  );
  const sessionIdentity =
    sessionSnapshot === null
      ? null
      : `${sessionSnapshot.userId}\u0000${sessionSnapshot.csrfToken}`;
  const [preference, setPreference] =
    useState<MyWorkInspectorPreference>(initial);
  const [status, setStatus] = useState<MyWorkInspectorPreferenceStatus>(
    sessionSnapshot ? "loading" : "unavailable",
  );
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [settledSessionIdentity, setSettledSessionIdentity] = useState<
    string | null
  >(null);
  const generation = useRef(0);
  const loaded = useRef(false);
  const confirmed = useRef<MyWorkInspectorPreference>(initial);
  const displayed = useRef<MyWorkInspectorPreference>(initial);
  const pending = useRef<readonly PendingPreference[]>([]);
  const activeRequest = useRef<ActiveSessionRequest | null>(null);
  const processingGeneration = useRef<number | null>(null);

  useEffect(() => {
    const requestGeneration = generation.current + 1;
    generation.current = requestGeneration;
    pending.current = [];
    loaded.current = false;
    processingGeneration.current = null;
    confirmed.current = initial;
    displayed.current = initial;

    const controller = new AbortController();
    if (sessionSnapshot === null || sessionIdentity === null) {
      activeRequest.current = null;
      return () => {
        controller.abort();
        if (generation.current === requestGeneration) {
          generation.current += 1;
        }
      };
    }

    const request: ActiveSessionRequest = {
      controller,
      generation: requestGeneration,
      identity: sessionIdentity,
      session: sessionSnapshot,
    };
    activeRequest.current = request;
    void dataSource
      .load(controller.signal)
      .then((response) => {
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration ||
          activeRequest.current !== request
        ) {
          return;
        }
        confirmed.current = response;
        displayed.current = response;
        loaded.current = true;
        setSettledSessionIdentity(sessionIdentity);
        setHasLoaded(true);
        setFailure(null);
        setPreference(response);
        setStatus("ready");
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          generation.current !== requestGeneration ||
          activeRequest.current !== request
        ) {
          return;
        }
        confirmed.current = initial;
        displayed.current = initial;
        loaded.current = false;
        setSettledSessionIdentity(sessionIdentity);
        setHasLoaded(false);
        setPreference(initial);
        setFailure(toRequestFailure(error));
        setStatus("failed");
      });

    return () => {
      controller.abort();
      if (activeRequest.current === request) {
        activeRequest.current = null;
      }
      if (generation.current === requestGeneration) {
        generation.current += 1;
      }
    };
  }, [dataSource, initial, loadAttempt, sessionIdentity, sessionSnapshot]);

  const processPending = useCallback(async (): Promise<void> => {
    const request = activeRequest.current;
    if (
      request === null ||
      processingGeneration.current === request.generation ||
      !loaded.current
    ) {
      return;
    }
    processingGeneration.current = request.generation;
    const isCurrentRequest = (): boolean =>
      generation.current === request.generation &&
      activeRequest.current === request &&
      !request.controller.signal.aborted;

    try {
      while (pending.current.length > 0) {
        const [operation, ...remaining] = pending.current;
        pending.current = remaining;
        if (!operation) continue;
        setFailure(null);
        setStatus("saving");
        try {
          const response = await dataSource.save(
            operation.command,
            request.session,
            request.controller.signal,
          );
          if (!isCurrentRequest()) return;
          confirmed.current = response;
          if (pending.current.length === 0) {
            displayed.current = response;
            setPreference(response);
          }
        } catch (error: unknown) {
          if (!isCurrentRequest()) return;
          pending.current = [];
          loaded.current = false;
          displayed.current = confirmed.current;
          setHasLoaded(false);
          setPreference(confirmed.current);
          setFailure(toRequestFailure(error));
          setStatus("failed");
          return;
        }
      }
      if (isCurrentRequest()) {
        displayed.current = confirmed.current;
        setPreference(confirmed.current);
        setStatus("ready");
      }
    } finally {
      if (processingGeneration.current === request.generation) {
        processingGeneration.current = null;
      }
    }
  }, [dataSource]);

  const update = useCallback(
    (next: UpdateMyWorkInspectorPreference): void => {
      const request = activeRequest.current;
      const command: unknown = {
        schemaVersion: myWorkInspectorSchemaVersion,
        ...next,
      };
      if (
        request?.identity !== sessionIdentity ||
        settledSessionIdentity !== sessionIdentity ||
        !loaded.current ||
        !isSaveMyWorkInspectorPreference(command)
      ) {
        return;
      }
      const nextPreference: MyWorkInspectorPreference = {
        ...displayed.current,
        collapsed: command.collapsed,
        widthPx: command.widthPx,
      };
      displayed.current = nextPreference;
      pending.current = [...pending.current, { command }];
      setPreference(nextPreference);
      setFailure(null);
      setStatus("saving");
      void processPending();
    },
    [processPending, sessionIdentity, settledSessionIdentity],
  );

  const reload = useCallback((): void => {
    if (sessionIdentity === null) return;
    const request = activeRequest.current;
    request?.controller.abort();
    activeRequest.current = null;
    pending.current = [];
    loaded.current = false;
    processingGeneration.current = null;
    generation.current += 1;
    setSettledSessionIdentity(null);
    setHasLoaded(false);
    setLoadAttempt((current) => current + 1);
  }, [sessionIdentity]);

  const stateBelongsToSession =
    sessionIdentity !== null && settledSessionIdentity === sessionIdentity;
  return {
    canUpdate: stateBelongsToSession && hasLoaded,
    failure: stateBelongsToSession ? failure : null,
    preference: stateBelongsToSession ? preference : initial,
    reload,
    status:
      sessionIdentity === null
        ? "unavailable"
        : stateBelongsToSession
          ? status
          : "loading",
    update,
  };
}
