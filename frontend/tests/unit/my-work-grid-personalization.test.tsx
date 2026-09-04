import { StrictMode, type ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  defaultMyWorkGridLayout,
  defaultMyWorkGridPreferences,
  myWorkTableSchemaVersion,
  type MyWorkGridPreferences,
  type MyWorkGridPreferencesDataSource,
} from "../../src/api/grid-preferences-data-source";
import { NpiApiError, NpiTransportError } from "../../src/api/http";
import {
  useMyWorkGridPersonalization,
  type UpdateMyWorkGridPreference,
} from "../../src/components/my-work-grid-personalization";
import type { SessionCommandContext } from "../../src/i18n/runtime";

const projectId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const session: SessionCommandContext = {
  csrfToken: "authenticated-csrf-token-fixture",
  userId: "engineer@example.invalid",
};

function preferenceFixture(version: number): MyWorkGridPreferences {
  return {
    ...structuredClone(defaultMyWorkGridPreferences()),
    version,
  };
}

function applyPreferenceUpdate(
  current: MyWorkGridPreferences,
  update: UpdateMyWorkGridPreference,
  version: number,
): MyWorkGridPreferences {
  return {
    ...current,
    defaultProjectId:
      update.defaultProjectId === undefined
        ? current.defaultProjectId
        : update.defaultProjectId,
    favoriteViewIds: update.favoriteViewIds ?? current.favoriteViewIds,
    recentViewIds: update.recentViewIds ?? current.recentViewIds,
    version,
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

function deferred<T>(): {
  promise: Promise<T>;
  reject: (reason: unknown) => void;
  resolve: (value: T) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

describe("My Work grid personalization controller", () => {
  it("loads and saves from the confirmed version after StrictMode effect replay", async () => {
    const loaded = preferenceFixture(4);
    const persisted = {
      ...loaded,
      favoriteViewIds: ["all"] as const,
      version: 5,
    };
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockResolvedValue(loaded);
    const save = vi
      .fn<MyWorkGridPreferencesDataSource["save"]>()
      .mockResolvedValue(persisted);
    const dataSource = { load, save };

    const { result } = renderHook(
      () =>
        useMyWorkGridPersonalization({
          dataSource,
          session,
        }),
      {
        wrapper: ({ children }: { children: ReactNode }) => (
          <StrictMode>{children}</StrictMode>
        ),
      },
    );

    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    act(() => {
      result.current.update({
        favoriteViewIds: ["all"],
        viewId: "all",
      });
    });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
      expect(save).toHaveBeenCalledTimes(1);
    });

    expect(load).toHaveBeenCalledTimes(2);
    expect(save.mock.calls[0]?.[0].expectedVersion).toBe(4);
    expect(result.current.preferences).toEqual(persisted);
  });

  it("loads the authenticated actor's confirmed preferences", async () => {
    const loaded = preferenceFixture(4);
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockResolvedValue(loaded);
    const save = vi.fn<MyWorkGridPreferencesDataSource["save"]>();
    const dataSource = { load, save };

    const { result } = renderHook(() =>
      useMyWorkGridPersonalization({
        dataSource,
        session,
      }),
    );

    expect(result.current.status).toBe("loading");
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });

    expect(result.current.preferences).toEqual(loaded);
    expect(result.current.loadEpoch).toBe(1);
    expect(result.current.failure).toBeNull();
    expect(load).toHaveBeenCalledTimes(1);
    const signal = load.mock.calls[0]?.[0];
    expect(signal).toBeInstanceOf(AbortSignal);
    expect(signal?.aborted).toBe(false);
    expect(save).not.toHaveBeenCalled();
  });

  it("clears a prior load failure after a manual reload succeeds", async () => {
    const loaded = preferenceFixture(6);
    const loadFailure = new NpiTransportError(
      "network",
      "request-grid-load-failure",
      "request",
    );
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockRejectedValueOnce(loadFailure)
      .mockResolvedValueOnce(loaded);
    const save = vi.fn<MyWorkGridPreferencesDataSource["save"]>();
    const dataSource = { load, save };

    const { result } = renderHook(() =>
      useMyWorkGridPersonalization({
        dataSource,
        session,
      }),
    );

    await waitFor(() => {
      expect(result.current.status).toBe("failed");
    });
    expect(result.current.failure).toEqual({
      kind: "network",
      referenceId: "request-grid-load-failure",
      referenceKind: "request",
    });

    act(() => {
      result.current.reload();
    });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });

    expect(load).toHaveBeenCalledTimes(2);
    expect(result.current.failure).toBeNull();
    expect(result.current.preferences).toEqual(loaded);
    expect(result.current.canUpdate).toBe(true);
    expect(save).not.toHaveBeenCalled();
  });

  it("does not expose a prior actor's preferences when the next actor's load fails", async () => {
    const firstLoaded: MyWorkGridPreferences = {
      ...preferenceFixture(8),
      defaultProjectId: projectId,
      favoriteViewIds: ["overdue"],
    };
    const nextSession: SessionCommandContext = {
      csrfToken: "failed-next-actor-csrf-token-fixture",
      userId: "failed-next-actor@example.invalid",
    };
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockResolvedValueOnce(firstLoaded)
      .mockRejectedValueOnce(
        new NpiTransportError(
          "network",
          "request-next-actor-load-failure",
          "request",
        ),
      );
    const save = vi.fn<MyWorkGridPreferencesDataSource["save"]>();
    const dataSource = { load, save };
    const initialProps: {
      activeSession: SessionCommandContext | null;
    } = {
      activeSession: session,
    };

    const { rerender, result } = renderHook(
      ({ activeSession }: { activeSession: SessionCommandContext | null }) =>
        useMyWorkGridPersonalization({
          dataSource,
          session: activeSession,
        }),
      { initialProps },
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    expect(result.current.preferences).toEqual(firstLoaded);

    rerender({ activeSession: nextSession });
    await waitFor(() => {
      expect(result.current.status).toBe("failed");
    });

    expect(load).toHaveBeenCalledTimes(2);
    expect(result.current.canUpdate).toBe(false);
    expect(result.current.preferences).toEqual(defaultMyWorkGridPreferences());
    expect(result.current.failure).toEqual({
      kind: "network",
      referenceId: "request-next-actor-load-failure",
      referenceKind: "request",
    });
    expect(save).not.toHaveBeenCalled();
  });

  it("ignores updates before the initial load and lets confirmed state win", async () => {
    const loadRequest = deferred<MyWorkGridPreferences>();
    const loaded: MyWorkGridPreferences = {
      ...preferenceFixture(4),
      defaultProjectId: projectId,
      favoriteViewIds: ["overdue"],
      recentViewIds: ["overdue"],
    };
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockImplementation(() => loadRequest.promise);
    const save = vi.fn<MyWorkGridPreferencesDataSource["save"]>();
    const dataSource = { load, save };

    const { result } = renderHook(() =>
      useMyWorkGridPersonalization({
        dataSource,
        session,
      }),
    );

    expect(result.current.status).toBe("loading");
    expect(result.current.canUpdate).toBe(false);
    act(() => {
      result.current.update({
        defaultProjectId: projectId,
        favoriteViewIds: ["today"],
        viewId: "today",
      });
    });
    expect(result.current.preferences).toEqual(defaultMyWorkGridPreferences());
    expect(save).not.toHaveBeenCalled();

    await act(async () => {
      loadRequest.resolve(loaded);
      await loadRequest.promise;
    });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    expect(result.current.canUpdate).toBe(true);
    expect(result.current.preferences).toEqual(loaded);
    expect(save).not.toHaveBeenCalled();
  });

  it("persists a new-session update while an old-generation save is still pending", async () => {
    const firstLoaded = preferenceFixture(4);
    const nextLoaded: MyWorkGridPreferences = {
      ...preferenceFixture(10),
      favoriteViewIds: ["today"],
      recentViewIds: ["today"],
    };
    const firstSave = deferred<MyWorkGridPreferences>();
    const nextSave = deferred<MyWorkGridPreferences>();
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockResolvedValueOnce(firstLoaded)
      .mockResolvedValueOnce(nextLoaded);
    const save = vi
      .fn<MyWorkGridPreferencesDataSource["save"]>()
      .mockImplementationOnce(() => firstSave.promise)
      .mockImplementationOnce(() => nextSave.promise);
    const dataSource = { load, save };
    const nextSession: SessionCommandContext = {
      csrfToken: "next-authenticated-csrf-token-fixture",
      userId: "next-engineer@example.invalid",
    };
    const firstUpdate: UpdateMyWorkGridPreference = {
      favoriteViewIds: ["all"],
      viewId: "all",
    };
    const nextUpdate: UpdateMyWorkGridPreference = {
      favoriteViewIds: ["overdue"],
      recentViewIds: ["overdue", "today"],
      viewId: "overdue",
    };
    const firstPersisted = applyPreferenceUpdate(firstLoaded, firstUpdate, 5);
    const nextPersisted = applyPreferenceUpdate(nextLoaded, nextUpdate, 11);

    const initialProps: {
      activeSession: SessionCommandContext | null;
    } = {
      activeSession: session,
    };
    const { rerender, result } = renderHook(
      ({ activeSession }: { activeSession: SessionCommandContext | null }) =>
        useMyWorkGridPersonalization({
          dataSource,
          session: activeSession,
        }),
      {
        initialProps,
      },
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    act(() => {
      result.current.update(firstUpdate);
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(1);
      expect(result.current.status).toBe("saving");
    });

    rerender({ activeSession: null });
    await waitFor(() => {
      expect(result.current.status).toBe("unavailable");
      expect(result.current.canUpdate).toBe(false);
    });
    rerender({ activeSession: nextSession });
    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(2);
      expect(result.current.status).toBe("ready");
      expect(result.current.preferences).toEqual(nextLoaded);
    });

    act(() => {
      result.current.update(nextUpdate);
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(2);
      expect(result.current.status).toBe("saving");
    });
    expect(save).toHaveBeenNthCalledWith(
      2,
      {
        defaultProjectId: null,
        expectedVersion: 10,
        favoriteViewIds: ["overdue"],
        filter: { priority: null, projectId: null, search: "" },
        layout: defaultMyWorkGridLayout(),
        recentViewIds: ["overdue", "today"],
        saveFilter: false,
        tableSchemaVersion: myWorkTableSchemaVersion,
        viewId: "overdue",
      },
      nextSession,
    );

    await act(async () => {
      nextSave.resolve(nextPersisted);
      await nextSave.promise;
    });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
      expect(result.current.preferences).toEqual(nextPersisted);
    });

    await act(async () => {
      firstSave.resolve(firstPersisted);
      await firstSave.promise;
    });
    expect(result.current.status).toBe("ready");
    expect(result.current.preferences).toEqual(nextPersisted);
  });

  it("queues exact writes against each server-confirmed version and settles on save success", async () => {
    const loaded = preferenceFixture(4);
    const firstSave = deferred<MyWorkGridPreferences>();
    const secondSave = deferred<MyWorkGridPreferences>();
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockResolvedValue(loaded);
    const save = vi
      .fn<MyWorkGridPreferencesDataSource["save"]>()
      .mockImplementationOnce(() => firstSave.promise)
      .mockImplementationOnce(() => secondSave.promise);
    const dataSource = { load, save };
    const firstLayout = {
      ...defaultMyWorkGridLayout(),
      fixedColumnCount: 1,
      hiddenColumnIds: ["assignment"] as const,
      widths: {
        ...defaultMyWorkGridLayout().widths,
        item: 318,
      },
    };
    const firstUpdate: UpdateMyWorkGridPreference = {
      defaultProjectId: projectId,
      favoriteViewIds: ["overdue"],
      filter: {
        priority: { scheme: "domain_severity", value: "high" },
        projectId,
        search: "runner",
      },
      layout: firstLayout,
      recentViewIds: ["overdue", "all"],
      viewId: "overdue",
    };
    const firstPersisted = applyPreferenceUpdate(loaded, firstUpdate, 5);
    const secondUpdate: UpdateMyWorkGridPreference = {
      filter: {
        priority: { scheme: "domain_severity", value: "critical" },
        projectId,
        search: "runner delivery",
      },
      recentViewIds: ["overdue", "today"],
      viewId: "overdue",
    };
    const secondPersisted = applyPreferenceUpdate(
      firstPersisted,
      secondUpdate,
      6,
    );

    const { result } = renderHook(() =>
      useMyWorkGridPersonalization({
        dataSource,
        session,
      }),
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });

    act(() => {
      result.current.update(firstUpdate);
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(1);
    });
    expect(result.current.status).toBe("saving");
    expect(
      result.current.preferences.viewLayouts.find(
        (candidate) => candidate.viewId === "overdue",
      ),
    ).toMatchObject({
      filter: firstUpdate.filter,
      layout: firstLayout,
    });
    expect(save).toHaveBeenNthCalledWith(
      1,
      {
        defaultProjectId: projectId,
        expectedVersion: 4,
        favoriteViewIds: ["overdue"],
        filter: firstUpdate.filter,
        layout: firstLayout,
        recentViewIds: ["overdue", "all"],
        saveFilter: true,
        tableSchemaVersion: myWorkTableSchemaVersion,
        viewId: "overdue",
      },
      session,
    );

    act(() => {
      result.current.update(secondUpdate);
    });
    expect(save).toHaveBeenCalledTimes(1);
    expect(
      result.current.preferences.viewLayouts.find(
        (candidate) => candidate.viewId === "overdue",
      )?.filter,
    ).toEqual(secondUpdate.filter);

    await act(async () => {
      firstSave.resolve(firstPersisted);
      await firstSave.promise;
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(2);
    });
    expect(save).toHaveBeenNthCalledWith(
      2,
      {
        defaultProjectId: projectId,
        expectedVersion: 5,
        favoriteViewIds: ["overdue"],
        filter: secondUpdate.filter,
        layout: firstLayout,
        recentViewIds: ["overdue", "today"],
        saveFilter: true,
        tableSchemaVersion: myWorkTableSchemaVersion,
        viewId: "overdue",
      },
      session,
    );

    await act(async () => {
      secondSave.resolve(secondPersisted);
      await secondSave.promise;
    });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    expect(result.current.preferences).toEqual(secondPersisted);
    expect(result.current.failure).toBeNull();
  });

  it("preserves filter intent and cross-view edits queued behind an active save", async () => {
    const loaded = preferenceFixture(4);
    const firstSave = deferred<MyWorkGridPreferences>();
    const secondSave = deferred<MyWorkGridPreferences>();
    const thirdSave = deferred<MyWorkGridPreferences>();
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockResolvedValue(loaded);
    const save = vi
      .fn<MyWorkGridPreferencesDataSource["save"]>()
      .mockImplementationOnce(() => firstSave.promise)
      .mockImplementationOnce(() => secondSave.promise)
      .mockImplementationOnce(() => thirdSave.promise);
    const dataSource = { load, save };
    const activeUpdate: UpdateMyWorkGridPreference = {
      favoriteViewIds: ["all"],
      viewId: "all",
    };
    const queuedFilterUpdate: UpdateMyWorkGridPreference = {
      filter: {
        priority: { scheme: "domain_severity", value: "critical" },
        projectId,
        search: "late evidence",
      },
      viewId: "overdue",
    };
    const todayLayout = {
      ...defaultMyWorkGridLayout(),
      fixedColumnCount: 1,
      hiddenColumnIds: ["assignment"] as const,
      widths: {
        ...defaultMyWorkGridLayout().widths,
        due: 168,
      },
    };
    const queuedCrossViewUpdate: UpdateMyWorkGridPreference = {
      layout: todayLayout,
      recentViewIds: ["today", "overdue"],
      viewId: "today",
    };
    const firstPersisted = applyPreferenceUpdate(loaded, activeUpdate, 5);
    const secondPersisted = applyPreferenceUpdate(
      firstPersisted,
      queuedFilterUpdate,
      6,
    );
    const thirdPersisted = applyPreferenceUpdate(
      secondPersisted,
      queuedCrossViewUpdate,
      7,
    );

    const { result } = renderHook(() =>
      useMyWorkGridPersonalization({
        dataSource,
        session,
      }),
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });

    act(() => {
      result.current.update(activeUpdate);
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(1);
    });

    act(() => {
      result.current.update(queuedFilterUpdate);
      result.current.update(queuedCrossViewUpdate);
    });
    expect(save).toHaveBeenCalledTimes(1);
    expect(
      result.current.preferences.viewLayouts.find(
        (candidate) => candidate.viewId === "overdue",
      )?.filter,
    ).toEqual(queuedFilterUpdate.filter);
    expect(
      result.current.preferences.viewLayouts.find(
        (candidate) => candidate.viewId === "today",
      )?.layout,
    ).toEqual(todayLayout);

    await act(async () => {
      firstSave.resolve(firstPersisted);
      await firstSave.promise;
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(2);
    });
    expect(save).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        expectedVersion: 5,
        filter: queuedFilterUpdate.filter,
        saveFilter: true,
        viewId: "overdue",
      }),
      session,
    );

    await act(async () => {
      secondSave.resolve(secondPersisted);
      await secondSave.promise;
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(3);
    });
    expect(save).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        expectedVersion: 6,
        layout: todayLayout,
        saveFilter: false,
        viewId: "today",
      }),
      session,
    );

    await act(async () => {
      thirdSave.resolve(thirdPersisted);
      await thirdSave.promise;
    });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    expect(result.current.preferences).toEqual(thirdPersisted);
    expect(result.current.failure).toBeNull();
  });

  it("coalesces adjacent same-view edits without dropping explicit filter intent", async () => {
    const loaded = preferenceFixture(10);
    const firstSave = deferred<MyWorkGridPreferences>();
    const mergedSave = deferred<MyWorkGridPreferences>();
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockResolvedValue(loaded);
    const save = vi
      .fn<MyWorkGridPreferencesDataSource["save"]>()
      .mockImplementationOnce(() => firstSave.promise)
      .mockImplementationOnce(() => mergedSave.promise);
    const dataSource = { load, save };
    const activeUpdate: UpdateMyWorkGridPreference = {
      favoriteViewIds: ["all"],
      viewId: "all",
    };
    const queuedFilterUpdate: UpdateMyWorkGridPreference = {
      filter: {
        priority: { scheme: "gate_requirement_priority", value: "P0" },
        projectId,
        search: "tool release",
      },
      viewId: "overdue",
    };
    const latestLayout = {
      ...defaultMyWorkGridLayout(),
      fixedColumnCount: 1,
      widths: {
        ...defaultMyWorkGridLayout().widths,
        item: 332,
      },
    };
    const queuedLayoutUpdate: UpdateMyWorkGridPreference = {
      layout: latestLayout,
      recentViewIds: ["overdue", "all"],
      viewId: "overdue",
    };
    const firstPersisted = applyPreferenceUpdate(loaded, activeUpdate, 11);
    const filterPersisted = applyPreferenceUpdate(
      firstPersisted,
      queuedFilterUpdate,
      12,
    );
    const mergedPersisted = applyPreferenceUpdate(
      filterPersisted,
      queuedLayoutUpdate,
      12,
    );

    const { result } = renderHook(() =>
      useMyWorkGridPersonalization({
        dataSource,
        session,
      }),
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });

    act(() => {
      result.current.update(activeUpdate);
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(1);
    });
    act(() => {
      result.current.update(queuedFilterUpdate);
      result.current.update(queuedLayoutUpdate);
    });
    expect(save).toHaveBeenCalledTimes(1);

    await act(async () => {
      firstSave.resolve(firstPersisted);
      await firstSave.promise;
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(2);
    });
    expect(save).toHaveBeenNthCalledWith(
      2,
      {
        defaultProjectId: null,
        expectedVersion: 11,
        favoriteViewIds: ["all"],
        filter: queuedFilterUpdate.filter,
        layout: latestLayout,
        recentViewIds: ["overdue", "all"],
        saveFilter: true,
        tableSchemaVersion: myWorkTableSchemaVersion,
        viewId: "overdue",
      },
      session,
    );

    await act(async () => {
      mergedSave.resolve(mergedPersisted);
      await mergedSave.promise;
    });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    expect(save).toHaveBeenCalledTimes(2);
    expect(result.current.preferences).toEqual(mergedPersisted);
    expect(result.current.failure).toBeNull();
  });

  it("reverts an optimistic update to the last confirmed state after a save failure", async () => {
    const loaded = preferenceFixture(7);
    const saveRequest = deferred<MyWorkGridPreferences>();
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockResolvedValue(loaded);
    const save = vi
      .fn<MyWorkGridPreferencesDataSource["save"]>()
      .mockImplementation(() => saveRequest.promise);
    const dataSource = { load, save };
    const failedLayout = {
      ...defaultMyWorkGridLayout(),
      fixedColumnCount: 0,
      widths: {
        ...defaultMyWorkGridLayout().widths,
        context: 310,
      },
    };

    const { result } = renderHook(() =>
      useMyWorkGridPersonalization({
        dataSource,
        session,
      }),
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });

    act(() => {
      result.current.update({
        layout: failedLayout,
        viewId: "all",
      });
    });
    await waitFor(() => {
      expect(result.current.status).toBe("saving");
    });
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ saveFilter: false }),
      session,
    );
    expect(
      result.current.preferences.viewLayouts.find(
        (candidate) => candidate.viewId === "all",
      )?.layout,
    ).toEqual(failedLayout);

    act(() => {
      saveRequest.reject(
        new NpiTransportError(
          "network",
          "request-grid-save-failure",
          "request",
        ),
      );
    });
    await waitFor(() => {
      expect(result.current.status).toBe("failed");
    });

    expect(result.current.preferences).toEqual(loaded);
    expect(result.current.failure).toEqual({
      kind: "network",
      referenceId: "request-grid-save-failure",
      referenceKind: "request",
    });
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("reloads and adopts server state after a version conflict", async () => {
    const loaded = preferenceFixture(2);
    const reconciled = applyPreferenceUpdate(
      loaded,
      {
        favoriteViewIds: ["approvals"],
        filter: {
          priority: { scheme: "gate_requirement_priority", value: "P0" },
          projectId: null,
          search: "evidence",
        },
        recentViewIds: ["approvals"],
        viewId: "approvals",
      },
      9,
    );
    const load = vi
      .fn<MyWorkGridPreferencesDataSource["load"]>()
      .mockResolvedValueOnce(loaded)
      .mockResolvedValueOnce(reconciled);
    const conflict = new NpiApiError({
      code: "PREFERENCE_VERSION_CONFLICT",
      retryable: true,
      status: 409,
      title: "The grid preference changed on another client.",
      traceId: "trace-grid-conflict",
      type: "urn:npi:problem:preference-version-conflict",
    });
    const save = vi
      .fn<MyWorkGridPreferencesDataSource["save"]>()
      .mockRejectedValue(conflict);
    const dataSource = { load, save };

    const { result } = renderHook(() =>
      useMyWorkGridPersonalization({
        dataSource,
        session,
      }),
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });

    act(() => {
      result.current.update({
        favoriteViewIds: ["overdue"],
        viewId: "overdue",
      });
    });
    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(2);
      expect(result.current.status).toBe("failed");
    });

    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ saveFilter: false }),
      session,
    );
    expect(load.mock.calls[1]).toEqual([]);
    expect(result.current.preferences).toEqual(reconciled);
    expect(result.current.loadEpoch).toBe(2);
    expect(result.current.failure).toMatchObject({
      kind: "problem",
      problem: {
        code: "PREFERENCE_VERSION_CONFLICT",
        status: 409,
        traceId: "trace-grid-conflict",
      },
      referenceId: "trace-grid-conflict",
      referenceKind: "trace",
    });
  });

  it("rejects session-null changes and reports persistence as unavailable", () => {
    const load = vi.fn<MyWorkGridPreferencesDataSource["load"]>();
    const save = vi.fn<MyWorkGridPreferencesDataSource["save"]>();
    const dataSource = { load, save };
    const localLayout = {
      ...defaultMyWorkGridLayout(),
      fixedColumnCount: 1,
      hiddenColumnIds: ["priority"] as const,
    };

    const { result } = renderHook(() =>
      useMyWorkGridPersonalization({
        dataSource,
        session: null,
      }),
    );

    expect(result.current.status).toBe("unavailable");
    act(() => {
      result.current.update({
        defaultProjectId: projectId,
        favoriteViewIds: ["today"],
        layout: localLayout,
        recentViewIds: ["today"],
        viewId: "today",
      });
    });

    expect(result.current.status).toBe("unavailable");
    expect(result.current.canUpdate).toBe(false);
    expect(result.current.failure).toBeNull();
    expect(result.current.preferences).toEqual(defaultMyWorkGridPreferences());
    expect(load).not.toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
  });
});
