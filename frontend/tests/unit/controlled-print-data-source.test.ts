import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isControlledPrintCapabilityResponse,
  isControlledPrintSnapshotResponse,
  LiveControlledPrintDataSource,
} from "../../src/api/controlled-print-data-source";
import {
  NpiHttpClient,
  NpiTransportError,
  type RequestOptions,
} from "../../src/api/http";
import {
  controlledPrintCapabilityFixture,
  controlledPrintProjectId,
  controlledPrintSnapshotId,
  controlledPrintSnapshotFixture,
  controlledPrintSourceFixture,
} from "../support/controlled-print-fixture";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("controlled-print closed response validation", () => {
  it("accepts exact capability and immutable snapshot truth", () => {
    expect(
      isControlledPrintCapabilityResponse(controlledPrintCapabilityFixture()),
    ).toBe(true);
    expect(
      isControlledPrintSnapshotResponse(controlledPrintSnapshotFixture()),
    ).toBe(true);
  });

  it.each([
    [
      "a private file URL",
      () => ({
        ...controlledPrintSnapshotFixture(),
        output: {
          ...controlledPrintSnapshotFixture().output,
          fileUrl: "/private/files/controlled-project-001.pdf",
        },
      }),
    ],
    [
      "a detached verification payload",
      () => ({
        ...controlledPrintSnapshotFixture(),
        verificationPayload: `urn:npi:controlled-print:81000000-0000-4000-8000-000000000099:${"c".repeat(64)}`,
      }),
    ],
    [
      "an unavailable capability that leaks a mapping",
      () => ({
        ...controlledPrintCapabilityFixture(false),
        registry: controlledPrintCapabilityFixture().registry,
      }),
    ],
  ])("rejects %s", (_name, build) => {
    const value = build();
    expect(
      "available" in value
        ? isControlledPrintCapabilityResponse(value)
        : isControlledPrintSnapshotResponse(value),
    ).toBe(false);
  });
});

describe("Live controlled-print data source", () => {
  it("loads only the exact capability route and query", async () => {
    const response = controlledPrintCapabilityFixture();
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request").mockResolvedValue(response);
    const source = new LiveControlledPrintDataSource(http);

    await expect(
      source.loadCapability(
        controlledPrintProjectId,
        controlledPrintSourceFixture(),
        "en",
        new AbortController().signal,
      ),
    ).resolves.toEqual(response);

    const [path, , options] = request.mock.calls[0] ?? [];
    expect(path).toBe(
      `/projects/${controlledPrintProjectId}/controlled-print/capability`,
    );
    expect(options).toMatchObject({
      query: {
        language: "en",
        sourceGlobalId: controlledPrintProjectId,
        sourceKind: "npi.project",
        sourceVersion: "3",
      },
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
  });

  it("creates only the closed source command and captures replay truth", async () => {
    const response = controlledPrintSnapshotFixture();
    const http = new NpiHttpClient();
    const implementation = <T>(
      path: string,
      init: RequestInit = {},
      options: RequestOptions<T> = {},
    ): Promise<T> => {
      expect(path).toBe(
        `/projects/${controlledPrintProjectId}/controlled-prints`,
      );
      expect(init.method).toBe("POST");
      const headers = new Headers({ "Idempotency-Replayed": "true" });
      expect(options.validateResponse?.(new Response(null, { headers }))).toBe(
        true,
      );
      return Promise.resolve(response as T);
    };
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(implementation);
    const source = new LiveControlledPrintDataSource(http);
    const commandContext = {
      csrfToken: "csrf-controlled-print-fixture-value",
      idempotencyKey: "controlled-print-fixture-0001",
      signal: new AbortController().signal,
    };

    await expect(
      source.createSnapshot(
        controlledPrintProjectId,
        controlledPrintSourceFixture(),
        "en",
        commandContext,
      ),
    ).resolves.toEqual({ replayed: true, snapshot: response });

    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(
      `/projects/${controlledPrintProjectId}/controlled-prints`,
    );
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(
      commandContext.idempotencyKey,
    );
    expect(options).toMatchObject({
      csrfToken: commandContext.csrfToken,
      requireIdempotencyReplay: true,
      requirePrivateNoStore: true,
    });
    expect(typeof init?.body).toBe("string");
    if (typeof init?.body !== "string") throw new Error("Expected JSON body.");
    expect(JSON.parse(init.body)).toEqual({
      ...controlledPrintSourceFixture(),
      language: "en",
    });
  });

  it("loads one retained snapshot only from its exact detail route", async () => {
    const response = controlledPrintSnapshotFixture();
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request").mockResolvedValue(response);
    const source = new LiveControlledPrintDataSource(http);

    await expect(
      source.loadSnapshot(
        controlledPrintProjectId,
        controlledPrintSnapshotId,
        new AbortController().signal,
      ),
    ).resolves.toEqual(response);

    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(
      `/projects/${controlledPrintProjectId}/controlled-prints/${controlledPrintSnapshotId}`,
    );
    expect(init?.method).toBeUndefined();
    expect(options).toMatchObject({
      requirePrivateNoStore: true,
      requireRequestIdEcho: true,
      requireTraceId: true,
    });
  });

  it("validates retained binary identity without using a private URL", async () => {
    const snapshot = controlledPrintSnapshotFixture();
    const blob = new Blob(["%PDF"], { type: "application/pdf" });
    const http = new NpiHttpClient();
    const implementation = <T>(
      path: string,
      init: RequestInit = {},
      options: RequestOptions<T> = {},
    ): Promise<T> => {
      expect(path).toBe(
        `/projects/${controlledPrintProjectId}/controlled-prints/${snapshot.globalId}/content`,
      );
      expect(init.method).toBeUndefined();
      const response = new Response(null, {
        headers: {
          "Content-Disposition":
            'attachment; filename="controlled-project-001.pdf"',
          "Content-Type": "application/pdf",
          "X-NPI-Output-Hash": snapshot.output.sha256,
          "X-NPI-Snapshot-Hash": snapshot.snapshotHash,
        },
      });
      const driftedResponse = new Response(null, {
        headers: {
          "Content-Disposition":
            'attachment; filename="controlled-project-001.pdf"',
          "Content-Type": "application/pdf",
          "X-NPI-Output-Hash": "f".repeat(64),
          "X-NPI-Snapshot-Hash": snapshot.snapshotHash,
        },
      });
      expect(options.validateResponse?.(driftedResponse)).toBe(false);
      expect(options.validateResponse?.(response)).toBe(true);
      expect(options.validate?.(blob)).toBe(true);
      return Promise.resolve(blob as T);
    };
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(implementation);
    const source = new LiveControlledPrintDataSource(http);

    await expect(
      source.download(
        controlledPrintProjectId,
        snapshot,
        new AbortController().signal,
      ),
    ).resolves.toEqual({
      blob,
      fileName: snapshot.output.fileName,
      outputHash: snapshot.output.sha256,
      snapshotHash: snapshot.snapshotHash,
    });
    expect(request.mock.calls[0]?.[0]).toBe(
      `/projects/${controlledPrintProjectId}/controlled-prints/${snapshot.globalId}/content`,
    );
  });

  it("rejects non-canonical identities and cancelled commands before transport", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveControlledPrintDataSource(http);
    const controller = new AbortController();
    controller.abort();

    await expect(
      source.loadCapability(
        "not-a-project",
        controlledPrintSourceFixture(),
        "en",
        new AbortController().signal,
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.createSnapshot(
        controlledPrintProjectId,
        controlledPrintSourceFixture(),
        "en",
        {
          csrfToken: "csrf-controlled-print-fixture-value",
          idempotencyKey: "controlled-print-fixture-0001",
          signal: controller.signal,
        },
      ),
    ).rejects.toThrow("cancelled");
    expect(request).not.toHaveBeenCalled();
  });
});
