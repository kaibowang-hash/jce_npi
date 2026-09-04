import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  FrappeMyWorkGridPreferencesDataSource,
  defaultMyWorkGridPreferences,
  myWorkTableSchemaVersion,
  type MyWorkGridFilter,
  type MyWorkGridLayout,
  type MyWorkGridPreferences,
  type MyWorkGridPreferencesDataSource,
  type MyWorkGridViewId,
} from "../api/grid-preferences-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { SessionCommandContext } from "../i18n/runtime";

export type MyWorkGridPreferenceStatus =
  | "failed"
  | "loading"
  | "ready"
  | "saving"
  | "unavailable";

export interface UpdateMyWorkGridPreference {
  readonly defaultProjectId?: string | null;
  readonly favoriteViewIds?: readonly MyWorkGridViewId[];
  readonly filter?: MyWorkGridFilter;
  readonly layout?: MyWorkGridLayout;
  readonly recentViewIds?: readonly MyWorkGridViewId[];
  readonly viewId: MyWorkGridViewId;
}

export interface MyWorkGridPersonalizationController {
  readonly canUpdate: boolean;
  readonly failure: RequestFailure | null;
  readonly loadEpoch: number;
  readonly preferences: MyWorkGridPreferences;
  readonly reload: () => void;
  readonly status: MyWorkGridPreferenceStatus;
  readonly update: (update: UpdateMyWorkGridPreference) => void;
}

interface PendingPreference {
  readonly preferences: MyWorkGridPreferences;
  readonly saveFilter: boolean;
  readonly viewId: MyWorkGridViewId;
}

function replaceViewPreference(
  current: MyWorkGridPreferences,
  update: UpdateMyWorkGridPreference,
): MyWorkGridPreferences {
  const currentView = current.viewLayouts.find(
    (candidate) => candidate.viewId === update.viewId,
  );
  if (!currentView) return current;
  return {
    ...current,
    defaultProjectId:
      update.defaultProjectId === undefined
        ? current.defaultProjectId
        : update.defaultProjectId,
    favoriteViewIds: update.favoriteViewIds ?? current.favoriteViewIds,
    recentViewIds: update.recentViewIds ?? current.recentViewIds,
    viewLayouts: current.viewLayouts.map((candidate) =>
      candidate.viewId === update.viewId
        ? {
            ...candidate,
            filter: update.filter ?? candidate.filter,
            hasSavedFilter:
              update.filter === undefined ? candidate.hasSavedFilter : true,
            layout: update.layout ?? candidate.layout,
          }
        : candidate,
    ),
  };
}

export function useMyWorkGridPersonalization({
  dataSource: suppliedDataSource,
  session,
}: {
  readonly dataSource?: MyWorkGridPreferencesDataSource;
  readonly session: SessionCommandContext | null;
}): MyWorkGridPersonalizationController {
  const dataSource = useMemo(
    () => suppliedDataSource ?? new FrappeMyWorkGridPreferencesDataSource(),
    [suppliedDataSource],
  );
  const initial = useMemo(() => defaultMyWorkGridPreferences(), []);
  const sessionIdentity =
    session === null ? null : `${session.userId}\u0000${session.csrfToken}`;
  const [preferences, setPreferences] =
    useState<MyWorkGridPreferences>(initial);
  const [status, setStatus] = useState<MyWorkGridPreferenceStatus>(
    session ? "loading" : "unavailable",
  );
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const [loadEpoch, setLoadEpoch] = useState(0);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [hasLoaded, setHasLoaded] = useState(false);
  const mounted = useRef(true);
  const loaded = useRef(false);
  const generation = useRef(0);
  const confirmed = useRef<MyWorkGridPreferences>(initial);
  const displayed = useRef<MyWorkGridPreferences>(initial);
  const pending = useRef<readonly PendingPreference[]>([]);
  const processingGeneration = useRef<number | null>(null);
  const [settledSessionIdentity, setSettledSessionIdentity] = useState<
    string | null
  >(null);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current += 1;
    };
  }, []);

  useEffect(() => {
    const requestGeneration = generation.current + 1;
    generation.current = requestGeneration;
    pending.current = [];
    loaded.current = false;
    const controller = new AbortController();
    if (!session) {
      confirmed.current = initial;
      displayed.current = initial;
      return () => {
        controller.abort();
      };
    }

    void dataSource
      .load(controller.signal)
      .then((response) => {
        if (
          controller.signal.aborted ||
          !mounted.current ||
          generation.current !== requestGeneration
        ) {
          return;
        }
        confirmed.current = response;
        displayed.current = response;
        loaded.current = true;
        setSettledSessionIdentity(sessionIdentity);
        setHasLoaded(true);
        setFailure(null);
        setPreferences(response);
        setStatus("ready");
        setLoadEpoch((current) => current + 1);
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          !mounted.current ||
          generation.current !== requestGeneration
        ) {
          return;
        }
        setSettledSessionIdentity(sessionIdentity);
        setHasLoaded(false);
        setPreferences(initial);
        setFailure(toRequestFailure(error));
        setStatus("failed");
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, initial, loadAttempt, session, sessionIdentity]);

  const processPending = useCallback(async (): Promise<void> => {
    const requestGeneration = generation.current;
    const isCurrentGeneration = (): boolean =>
      mounted.current && generation.current === requestGeneration;
    const hasPendingPreference = (): boolean => pending.current.length > 0;
    if (
      processingGeneration.current === requestGeneration ||
      !session ||
      !loaded.current
    ) {
      return;
    }
    processingGeneration.current = requestGeneration;
    try {
      while (pending.current.length > 0) {
        const [operation, ...remaining] = pending.current;
        pending.current = remaining;
        if (!operation) continue;
        const selected = operation.preferences.viewLayouts.find(
          (candidate) => candidate.viewId === operation.viewId,
        );
        if (!selected) continue;
        setFailure(null);
        setStatus("saving");
        try {
          const response = await dataSource.save(
            {
              defaultProjectId: operation.preferences.defaultProjectId,
              expectedVersion: confirmed.current.version,
              favoriteViewIds: operation.preferences.favoriteViewIds,
              filter: selected.filter,
              layout: selected.layout,
              recentViewIds: operation.preferences.recentViewIds,
              saveFilter: operation.saveFilter,
              tableSchemaVersion: myWorkTableSchemaVersion,
              viewId: operation.viewId,
            },
            session,
          );
          if (!isCurrentGeneration()) return;
          confirmed.current = response;
          if (!hasPendingPreference()) {
            displayed.current = response;
            setPreferences(response);
          }
        } catch (error: unknown) {
          if (!isCurrentGeneration()) return;
          pending.current = [];
          const requestFailure = toRequestFailure(error);
          loaded.current = false;
          setHasLoaded(false);
          displayed.current = confirmed.current;
          setPreferences(confirmed.current);
          setFailure(requestFailure);
          if (requestFailure.problem?.status === 409) {
            try {
              const reconciled = await dataSource.load();
              if (!isCurrentGeneration()) return;
              confirmed.current = reconciled;
              displayed.current = reconciled;
              loaded.current = true;
              setHasLoaded(true);
              setPreferences(reconciled);
              setLoadEpoch((current) => current + 1);
            } catch (reloadError: unknown) {
              if (!isCurrentGeneration()) return;
              setFailure(toRequestFailure(reloadError));
            }
          }
          setStatus("failed");
          return;
        }
      }
      if (isCurrentGeneration()) {
        displayed.current = confirmed.current;
        setPreferences(confirmed.current);
        setStatus("ready");
      }
    } finally {
      if (processingGeneration.current === requestGeneration) {
        processingGeneration.current = null;
      }
      if (hasPendingPreference() && isCurrentGeneration()) {
        void processPending();
      }
    }
  }, [dataSource, session]);

  const update = useCallback(
    (preferenceUpdate: UpdateMyWorkGridPreference): void => {
      if (!session || !loaded.current) {
        if (!session) setStatus("unavailable");
        return;
      }
      const next = replaceViewPreference(displayed.current, preferenceUpdate);
      displayed.current = next;
      setPreferences(next);
      setFailure(null);
      const nextPending: PendingPreference = {
        preferences: next,
        saveFilter: preferenceUpdate.filter !== undefined,
        viewId: preferenceUpdate.viewId,
      };
      const tail = pending.current.at(-1);
      pending.current =
        tail?.viewId === nextPending.viewId
          ? [
              ...pending.current.slice(0, -1),
              {
                ...nextPending,
                saveFilter: tail.saveFilter || nextPending.saveFilter,
              },
            ]
          : [...pending.current, nextPending];
      void processPending();
    },
    [processPending, session],
  );

  const stateBelongsToSession =
    sessionIdentity !== null && settledSessionIdentity === sessionIdentity;
  return {
    canUpdate: stateBelongsToSession && hasLoaded,
    failure: stateBelongsToSession ? failure : null,
    loadEpoch,
    preferences: stateBelongsToSession ? preferences : initial,
    reload: () => {
      loaded.current = false;
      setSettledSessionIdentity(null);
      setHasLoaded(false);
      setLoadAttempt((current) => current + 1);
    },
    status:
      sessionIdentity === null
        ? "unavailable"
        : stateBelongsToSession
          ? status
          : "loading",
    update,
  };
}
