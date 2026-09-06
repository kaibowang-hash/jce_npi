import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  defaultMyWorkInspectorPreference,
  myWorkInspectorSchemaVersion,
  type MyWorkInspectorPreference,
  type MyWorkInspectorPreferencesDataSource,
} from "../../src/api/my-work-inspector-preferences-data-source";
import { NpiTransportError } from "../../src/api/http";
import { useMyWorkInspectorPersonalization } from "../../src/components/my-work-inspector-personalization";
import type { SessionCommandContext } from "../../src/i18n/runtime";

const session: SessionCommandContext = {
  csrfToken: "authenticated-inspector-csrf-fixture",
  userId: "engineer@example.invalid",
};

function preferenceFixture(
  widthPx: number,
  collapsed = false,
): MyWorkInspectorPreference {
  return {
    ...defaultMyWorkInspectorPreference(),
    collapsed,
    widthPx,
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

describe("My Work inspector personalization controller", () => {
  it("is unavailable without a session and never touches browser storage", () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem");
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const load = vi.fn<MyWorkInspectorPreferencesDataSource["load"]>();
    const save = vi.fn<MyWorkInspectorPreferencesDataSource["save"]>();
    const { result } = renderHook(() =>
      useMyWorkInspectorPersonalization({
        dataSource: { load, save },
        session: null,
      }),
    );

    expect(result.current).toMatchObject({
      canUpdate: false,
      failure: null,
      preference: defaultMyWorkInspectorPreference(),
      status: "unavailable",
    });
    act(() => {
      result.current.update({ collapsed: true, widthPx: 400 });
      result.current.reload();
    });
    expect(load).not.toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
  });

  it("never exposes or restores a previous actor's inspector state", async () => {
    const firstPreference = preferenceFixture(420, true);
    const nextLoad = deferred<MyWorkInspectorPreference>();
    const load = vi
      .fn<MyWorkInspectorPreferencesDataSource["load"]>()
      .mockResolvedValueOnce(firstPreference)
      .mockImplementationOnce(() => nextLoad.promise);
    const save = vi.fn<MyWorkInspectorPreferencesDataSource["save"]>();
    const dataSource = { load, save };
    const nextSession: SessionCommandContext = {
      csrfToken: "next-actor-inspector-csrf-fixture",
      userId: "next-engineer@example.invalid",
    };
    const { rerender, result } = renderHook(
      ({ activeSession }: { activeSession: SessionCommandContext | null }) =>
        useMyWorkInspectorPersonalization({
          dataSource,
          session: activeSession,
        }),
      { initialProps: { activeSession: session } },
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    expect(result.current.preference).toEqual(firstPreference);

    rerender({ activeSession: nextSession });
    expect(result.current.status).toBe("loading");
    expect(result.current.canUpdate).toBe(false);
    expect(result.current.preference).toEqual(
      defaultMyWorkInspectorPreference(),
    );
    act(() => {
      result.current.update({ collapsed: true, widthPx: 460 });
    });
    expect(save).not.toHaveBeenCalled();

    await act(async () => {
      nextLoad.reject(
        new NpiTransportError(
          "network",
          "request-next-actor-inspector",
          "request",
        ),
      );
      await nextLoad.promise.catch(() => undefined);
    });
    await waitFor(() => {
      expect(result.current.status).toBe("failed");
    });
    expect(result.current.preference).toEqual(
      defaultMyWorkInspectorPreference(),
    );
    expect(result.current.failure).toEqual({
      kind: "network",
      referenceId: "request-next-actor-inspector",
      referenceKind: "request",
    });
  });

  it("serializes writes while preserving the latest optimistic preference", async () => {
    const loaded = preferenceFixture(340);
    const firstSave = deferred<MyWorkInspectorPreference>();
    const secondSave = deferred<MyWorkInspectorPreference>();
    const firstConfirmed = preferenceFixture(380);
    const secondConfirmed = preferenceFixture(420, true);
    const load = vi
      .fn<MyWorkInspectorPreferencesDataSource["load"]>()
      .mockResolvedValue(loaded);
    const save = vi
      .fn<MyWorkInspectorPreferencesDataSource["save"]>()
      .mockImplementationOnce(() => firstSave.promise)
      .mockImplementationOnce(() => secondSave.promise);
    const dataSource = { load, save };
    const { result } = renderHook(() =>
      useMyWorkInspectorPersonalization({ dataSource, session }),
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });

    act(() => {
      result.current.update({ collapsed: false, widthPx: 380 });
      result.current.update({ collapsed: true, widthPx: 420 });
    });
    expect(result.current.status).toBe("saving");
    expect(result.current.preference).toMatchObject({
      collapsed: true,
      widthPx: 420,
    });
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenNthCalledWith(
      1,
      {
        collapsed: false,
        schemaVersion: myWorkInspectorSchemaVersion,
        widthPx: 380,
      },
      session,
      expect.any(AbortSignal),
    );

    await act(async () => {
      firstSave.resolve(firstConfirmed);
      await firstSave.promise;
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(2);
    });
    expect(result.current.preference).toMatchObject({
      collapsed: true,
      widthPx: 420,
    });
    expect(save).toHaveBeenNthCalledWith(
      2,
      {
        collapsed: true,
        schemaVersion: myWorkInspectorSchemaVersion,
        widthPx: 420,
      },
      session,
      expect.any(AbortSignal),
    );

    await act(async () => {
      secondSave.resolve(secondConfirmed);
      await secondSave.promise;
    });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    expect(result.current.preference).toEqual(secondConfirmed);
    expect(result.current.canUpdate).toBe(true);
  });

  it("rolls back a failed write and requires reload before an explicit retry", async () => {
    const loaded = preferenceFixture(360);
    const reloaded = preferenceFixture(380);
    const retryConfirmed = preferenceFixture(400, true);
    const reloadRequest = deferred<MyWorkInspectorPreference>();
    const load = vi
      .fn<MyWorkInspectorPreferencesDataSource["load"]>()
      .mockResolvedValueOnce(loaded)
      .mockImplementationOnce(() => reloadRequest.promise);
    const save = vi
      .fn<MyWorkInspectorPreferencesDataSource["save"]>()
      .mockRejectedValueOnce(
        new NpiTransportError(
          "network",
          "request-inspector-save-failure",
          "request",
        ),
      )
      .mockResolvedValueOnce(retryConfirmed);
    const dataSource = { load, save };
    const { result } = renderHook(() =>
      useMyWorkInspectorPersonalization({ dataSource, session }),
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });

    act(() => {
      result.current.update({ collapsed: true, widthPx: 440 });
    });
    expect(result.current.preference).toMatchObject({
      collapsed: true,
      widthPx: 440,
    });
    await waitFor(() => {
      expect(result.current.status).toBe("failed");
    });
    expect(result.current.preference).toEqual(loaded);
    expect(result.current.canUpdate).toBe(false);
    expect(result.current.failure).toEqual({
      kind: "network",
      referenceId: "request-inspector-save-failure",
      referenceKind: "request",
    });
    expect(load).toHaveBeenCalledTimes(1);

    act(() => {
      result.current.update({ collapsed: true, widthPx: 400 });
    });
    expect(save).toHaveBeenCalledTimes(1);
    expect(load).toHaveBeenCalledTimes(1);

    act(() => {
      result.current.reload();
    });
    expect(result.current.status).toBe("loading");
    expect(result.current.canUpdate).toBe(false);
    expect(result.current.preference).toEqual(
      defaultMyWorkInspectorPreference(),
    );
    expect(save).toHaveBeenCalledTimes(1);
    await act(async () => {
      reloadRequest.resolve(reloaded);
      await reloadRequest.promise;
    });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    expect(result.current.preference).toEqual(reloaded);

    act(() => {
      result.current.update({ collapsed: true, widthPx: 400 });
    });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
      expect(save).toHaveBeenCalledTimes(2);
    });
    expect(result.current.preference).toEqual(retryConfirmed);
  });

  it("ignores an old actor's save completion after a session switch", async () => {
    const firstLoaded = preferenceFixture(340);
    const nextLoaded = preferenceFixture(300);
    const oldSave = deferred<MyWorkInspectorPreference>();
    const load = vi
      .fn<MyWorkInspectorPreferencesDataSource["load"]>()
      .mockResolvedValueOnce(firstLoaded)
      .mockResolvedValueOnce(nextLoaded);
    const save = vi
      .fn<MyWorkInspectorPreferencesDataSource["save"]>()
      .mockImplementation(() => oldSave.promise);
    const dataSource = { load, save };
    const nextSession: SessionCommandContext = {
      csrfToken: "switch-actor-inspector-csrf-fixture",
      userId: "switch-engineer@example.invalid",
    };
    const { rerender, result } = renderHook(
      ({ activeSession }: { activeSession: SessionCommandContext | null }) =>
        useMyWorkInspectorPersonalization({
          dataSource,
          session: activeSession,
        }),
      { initialProps: { activeSession: session } },
    );
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    act(() => {
      result.current.update({ collapsed: true, widthPx: 460 });
    });
    await waitFor(() => {
      expect(save).toHaveBeenCalledTimes(1);
    });

    rerender({ activeSession: nextSession });
    await waitFor(() => {
      expect(result.current.status).toBe("ready");
    });
    expect(result.current.preference).toEqual(nextLoaded);

    await act(async () => {
      oldSave.resolve(preferenceFixture(460, true));
      await oldSave.promise;
    });
    expect(result.current.status).toBe("ready");
    expect(result.current.preference).toEqual(nextLoaded);
  });
});
