import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isToolingExportPackage,
  isToolingListPage,
  isToolingListPreference,
  LiveToolingListDataSource,
} from "../../src/api/tooling-list-data-source";
import { NpiTransportError } from "../../src/api/http";
import {
  toolingExportPackage,
  toolingListFilter,
  toolingListIds,
  toolingListPage,
  toolingListPreference,
} from "../support/tooling-list-fixture";

function governedHeaders(init?: RequestInit): Record<string, string> {
  const requestHeaders = new Headers(init?.headers);
  return {
    "Cache-Control": "private, no-store",
    "Content-Type": "application/json",
    "X-Request-ID": requestHeaders.get("X-Request-ID") ?? "",
    "X-Trace-ID": "trace-tooling-list-test",
  };
}

function requestUrl(request: RequestInfo | URL | undefined): string {
  if (typeof request === "string") return request;
  if (request instanceof URL) return request.href;
  return request?.url ?? "";
}

function bodyText(body: BodyInit | null | undefined): string {
  if (typeof body !== "string")
    throw new Error("An exact JSON request body is required.");
  return body;
}

function jsonResponse(
  value: unknown,
  init?: RequestInit,
  options: { replayed?: boolean; status?: number } = {},
): Response {
  return new Response(JSON.stringify(value), {
    headers: {
      ...governedHeaders(init),
      ...(options.replayed === undefined
        ? {}
        : { "Idempotency-Replayed": String(options.replayed) }),
    },
    status: options.status ?? 200,
  });
}

function commandContext(suffix: string) {
  return {
    csrfToken: "c".repeat(32),
    idempotencyKey: `tooling-list-${suffix}-12345678`,
    signal: new AbortController().signal,
  };
}

async function hashBytes(bytes: Uint8Array): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    bytes.slice().buffer,
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Tooling List data source", () => {
  it("accepts only exact bounded list, preference and package snapshots", () => {
    const page = toolingListPage();
    const preference = toolingListPreference();
    const packageValue = toolingExportPackage();

    expect(isToolingListPage(page)).toBe(true);
    expect(isToolingListPreference(preference)).toBe(true);
    expect(isToolingExportPackage(packageValue)).toBe(true);
    expect(isToolingListPage({ ...page, privateFileId: "hidden" })).toBe(false);
    expect(
      isToolingListPage({
        ...page,
        items: [page.items[0], page.items[0]],
      }),
    ).toBe(false);
    expect(
      isToolingListPreference({
        ...preference,
        preference: {
          ...preference.preference,
          columnOrder: [
            ...preference.preference.columnOrder.slice(0, -1),
            "tooling",
          ],
        },
      }),
    ).toBe(false);
    expect(
      isToolingExportPackage({
        ...packageValue,
        expiresAt: "2026-08-10T10:00:01Z",
      }),
    ).toBe(false);
  });

  it("loads a stable server page and saves only the selected personal view", async () => {
    const savedPreference = toolingListPreference();
    const fetch = vi.fn<typeof globalThis.fetch>((request, init) => {
      const url = requestUrl(request);
      return Promise.resolve(
        jsonResponse(
          url.includes("/preferences/") ? savedPreference : toolingListPage(),
          init,
        ),
      );
    });
    vi.stubGlobal("fetch", fetch);
    const source = new LiveToolingListDataSource();
    const filter = toolingListFilter();

    await source.loadList(
      toolingListIds.project,
      filter,
      50,
      null,
      new AbortController().signal,
    );
    await source.loadPreference(
      toolingListIds.project,
      "all",
      new AbortController().signal,
    );
    await source.savePreference(
      toolingListIds.project,
      "all",
      {
        expectedSnapshotHash: "d".repeat(64),
        expectedVersion: 1,
        preference: savedPreference.preference,
      },
      "c".repeat(32),
      new AbortController().signal,
    );

    expect(requestUrl(fetch.mock.calls[0]?.[0])).toBe(
      `/api/npi/v1/projects/${toolingListIds.project}/tooling-list?groupKey=none&pageSize=50&search=&sortDirection=asc&sortKey=title&viewId=all`,
    );
    expect(requestUrl(fetch.mock.calls[1]?.[0])).toBe(
      `/api/npi/v1/projects/${toolingListIds.project}/tooling-list/preferences/all`,
    );
    expect(requestUrl(fetch.mock.calls[2]?.[0])).toBe(
      `/api/npi/v1/projects/${toolingListIds.project}/tooling-list/preferences/all`,
    );
    const saveInit = fetch.mock.calls[2]?.[1];
    expect(saveInit?.method).toBe("PUT");
    expect(new Headers(saveInit?.headers).get("X-Frappe-CSRF-Token")).toBe(
      "c".repeat(32),
    );
    expect(JSON.parse(bodyText(saveInit?.body)) as unknown).toMatchObject({
      expectedSnapshotHash: "d".repeat(64),
      expectedVersion: 1,
    });
  });

  it("creates and downloads an actor-bound package with exact replay and byte validation", async () => {
    const bytes = new TextEncoder().encode("exact tooling package bytes");
    const blob = new Blob([bytes], { type: "application/zip" });
    Object.defineProperty(blob, "arrayBuffer", {
      value: () => Promise.resolve(bytes.slice().buffer),
    });
    Object.defineProperty(blob, "text", {
      value: () => Promise.resolve("exact tooling package bytes"),
    });
    const fixtureReference = toolingExportPackage().objectRefs[0];
    if (!fixtureReference)
      throw new Error("An exact fixture reference is required.");
    const packageValue = toolingExportPackage({
      objectCount: 1,
      objectRefs: [fixtureReference],
      sha256: await hashBytes(bytes),
      sizeBytes: blob.size,
    });
    const fetch = vi.fn<typeof globalThis.fetch>((request, init) => {
      const url = requestUrl(request);
      if (url.endsWith(":content")) {
        const response = new Response(null, {
          headers: {
            ...governedHeaders(init),
            "Content-Disposition": `attachment; filename="${packageValue.fileName}"`,
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Content-Type": "application/zip",
            "Idempotency-Replayed": "true",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
          },
          status: 200,
        });
        Object.defineProperty(response, "blob", {
          value: () => Promise.resolve(blob),
        });
        return Promise.resolve(response);
      }
      return Promise.resolve(
        jsonResponse({ package: packageValue }, init, {
          replayed: true,
          status: 201,
        }),
      );
    });
    vi.stubGlobal("fetch", fetch);
    const source = new LiveToolingListDataSource();
    const reference = packageValue.objectRefs[0];
    if (!reference) throw new Error("An exact package reference is required.");

    const created = await source.createExport(
      toolingListIds.project,
      { mode: "selection", selection: [reference] },
      commandContext("create"),
    );
    const downloaded = await source.downloadExport(
      toolingListIds.project,
      packageValue,
      commandContext("download"),
    );

    expect(created).toEqual({ package: packageValue, replayed: true });
    expect(downloaded.fileName).toBe(packageValue.fileName);
    expect(downloaded.replayed).toBe(true);
    expect(await downloaded.blob.text()).toBe("exact tooling package bytes");
    const createInit = fetch.mock.calls[0]?.[1];
    expect(new Headers(createInit?.headers).get("Idempotency-Key")).toBe(
      "tooling-list-create-12345678",
    );
    expect(JSON.parse(bodyText(createInit?.body)) as unknown).toEqual({
      mode: "selection",
      selection: [reference],
    });
    const downloadInit = fetch.mock.calls[1]?.[1];
    expect(JSON.parse(bodyText(downloadInit?.body)) as unknown).toEqual({
      expectedSnapshotHash: packageValue.snapshotHash,
    });
  });

  it("fails closed before transport for invalid filters and package references", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>();
    vi.stubGlobal("fetch", fetch);
    const source = new LiveToolingListDataSource();

    await expect(
      source.loadList(
        toolingListIds.project,
        { ...toolingListFilter(), search: "invalid\nsearch" },
        50,
        null,
        new AbortController().signal,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.downloadExport(
        toolingListIds.originProject,
        toolingExportPackage(),
        commandContext("download"),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(fetch).not.toHaveBeenCalled();
  });
});
