import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DocumentRequestCancelledError,
  isControlledDocumentPageResponse,
  isControlledDocumentWorkspaceResponse,
  isDocumentFileCapabilityResponse,
  LiveDocumentDataSource,
  type ControlledDocumentWorkspaceViewModel,
} from "../../src/api/document-data-source";
import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  controlledDocumentId,
  controlledDocumentPageFixture,
  controlledDocumentWorkspaceFixture,
  documentFileCapabilityFixture,
  documentProjectId,
  documentRevisionId,
  fileRevisionId,
} from "../support/document-fixture";

function commandContext(signal = new AbortController().signal) {
  return {
    csrfToken: "csrf-document-fixture",
    idempotencyKey: "document-command-key",
    signal,
  };
}

function workspaceWith(
  overrides: Partial<ControlledDocumentWorkspaceViewModel["document"]>,
): ControlledDocumentWorkspaceViewModel {
  const fixture = controlledDocumentWorkspaceFixture();
  return {
    ...fixture,
    document: {
      ...fixture.document,
      ...overrides,
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("controlled document response validation", () => {
  it("accepts the exact closed page, workspace, and capability contracts", () => {
    expect(
      isControlledDocumentPageResponse(controlledDocumentPageFixture()),
    ).toBe(true);
    expect(
      isControlledDocumentWorkspaceResponse(
        controlledDocumentWorkspaceFixture(),
      ),
    ).toBe(true);
    expect(
      isDocumentFileCapabilityResponse(documentFileCapabilityFixture()),
    ).toBe(true);
  });

  it.each([
    [
      "an undeclared top-level field",
      () => ({
        ...controlledDocumentPageFixture(),
        privateFileUrl: "/private/files/synthetic-drawing.pdf",
      }),
    ],
    [
      "a duplicated document identity",
      () => {
        const fixture = controlledDocumentPageFixture();
        return { ...fixture, items: [fixture.items[0], fixture.items[0]] };
      },
    ],
    [
      "external retrieval represented as available",
      () => ({
        ...controlledDocumentWorkspaceFixture(),
        externalRetrieval: {
          state: "available",
          reasonCode: "share_grant_present",
        },
      }),
    ],
    [
      "a current revision not present in immutable history",
      () =>
        workspaceWith({
          currentRevision: {
            globalId: "72000000-0000-4000-8000-000000000001",
            major: 1,
            minor: 0,
            snapshotHash: "b".repeat(64),
          },
        }),
    ],
  ])("rejects %s", (_name, build) => {
    const value = build();
    expect(
      "items" in value
        ? isControlledDocumentPageResponse(value)
        : isControlledDocumentWorkspaceResponse(value),
    ).toBe(false);
  });

  it("rejects capability identity drift and unsafe preview claims", () => {
    const capability = documentFileCapabilityFixture();
    expect(
      isDocumentFileCapabilityResponse({
        ...capability,
        fileRevisionId: "72000000-0000-4000-8000-000000000002",
      }),
    ).toBe(false);
    expect(
      isDocumentFileCapabilityResponse({
        ...capability,
        capabilities: {
          ...capability.capabilities,
          preview: {
            state: "blocked",
            reasonCode: "scan_pending",
            mode: "native_pdf",
          },
        },
      }),
    ).toBe(false);
  });
});

describe("live controlled document data source", () => {
  it("loads an exact bounded Project document page through the BFF", async () => {
    const fixture = controlledDocumentPageFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(fixture as T));
    const source = new LiveDocumentDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.loadDocuments(documentProjectId, signal, { limit: 25 }),
    ).resolves.toEqual(fixture);
    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(`/projects/${documentProjectId}/documents`);
    expect(init).toEqual({ signal });
    expect(options?.query).toEqual({ limit: "25" });
    expect(options?.requirePrivateNoStore).toBe(true);
    expect(options?.requireRequestIdEcho).toBe(true);
    expect(options?.requireTraceId).toBe(true);
    expect(options?.validate?.(fixture)).toBe(true);
    expect(
      options?.validate?.({
        ...fixture,
        project: {
          ...fixture.project,
          globalId: "72000000-0000-4000-8000-000000000003",
        },
      }),
    ).toBe(false);
  });

  it("encodes only the closed typed relationship filter", async () => {
    const fixture = controlledDocumentPageFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(fixture as T));

    await new LiveDocumentDataSource(http).loadDocuments(
      documentProjectId,
      new AbortController().signal,
      {
        relationshipKind: "project_reference",
        targetIdentity: "ERP-CUSTOMER-071",
        targetVersion: 2,
        projectReferenceType: "customer",
        targetSourceSystem: "ERPNEXT",
        targetReferenceGlobalId: "72000000-0000-4000-8000-000000000004",
      },
    );

    expect(request.mock.calls[0]?.[2]?.query).toEqual({
      limit: "50",
      relationshipKind: "project_reference",
      targetIdentity: "ERP-CUSTOMER-071",
      targetVersion: "2",
      projectReferenceType: "customer",
      targetSourceSystem: "ERPNEXT",
      targetReferenceGlobalId: "72000000-0000-4000-8000-000000000004",
    });
  });

  it.each([
    [
      "an invalid Project ID",
      () =>
        new LiveDocumentDataSource().loadDocuments(
          "not-a-uuid",
          new AbortController().signal,
        ),
    ],
    [
      "a partial relationship filter",
      () =>
        new LiveDocumentDataSource().loadDocuments(
          documentProjectId,
          new AbortController().signal,
          { relationshipKind: "gate" },
        ),
    ],
    [
      "a raw filter expression",
      () =>
        new LiveDocumentDataSource().loadDocuments(
          documentProjectId,
          new AbortController().signal,
          {
            relationshipKind: "project_reference",
            targetIdentity: "customer = *",
            targetVersion: 1,
          },
        ),
    ],
  ])("rejects %s before fetch", async (_name, makeRequest) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(makeRequest()).rejects.toBeInstanceOf(NpiTransportError);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("loads an exact document workspace and capability result", async () => {
    const workspace = controlledDocumentWorkspaceFixture();
    const capability = documentFileCapabilityFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(workspace)
      .mockResolvedValueOnce(capability);
    const source = new LiveDocumentDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.loadDocument(documentProjectId, controlledDocumentId, signal),
    ).resolves.toEqual(workspace);
    await expect(
      source.loadCapabilities(
        documentProjectId,
        controlledDocumentId,
        documentRevisionId,
        fileRevisionId,
        signal,
      ),
    ).resolves.toEqual(capability);
    expect(request.mock.calls[0]?.[0]).toBe(
      `/projects/${documentProjectId}/documents/${controlledDocumentId}`,
    );
    expect(request.mock.calls[1]?.[0]).toBe(
      `/projects/${documentProjectId}/documents/${controlledDocumentId}/revisions/${documentRevisionId}/files/${fileRevisionId}/capabilities`,
    );
  });

  it("submits a versioned check-out command with independent CSRF and idempotency", async () => {
    const workspace = controlledDocumentWorkspaceFixture();
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(workspace as T));
    const source = new LiveDocumentDataSource(http);
    const context = commandContext();

    await expect(
      source.checkOut(documentProjectId, controlledDocumentId, 2, context),
    ).resolves.toEqual(workspace);
    const [path, init, options] = request.mock.calls[0] ?? [];
    expect(path).toBe(
      `/projects/${documentProjectId}/documents/${controlledDocumentId}:check-out`,
    );
    const body = init?.body;
    if (typeof body !== "string")
      throw new Error("The check-out body was not JSON.");
    const parsedBody: unknown = JSON.parse(body);
    expect(parsedBody).toEqual({
      expectedDocumentVersion: 2,
    });
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(
      context.idempotencyKey,
    );
    expect(options?.csrfToken).toBe(context.csrfToken);
    expect(options?.requireIdempotencyReplay).toBe(true);
    expect(options?.validate?.(workspace)).toBe(true);
    expect(
      options?.validate?.(
        workspaceWith({
          optimisticVersion: 4,
        }),
      ),
    ).toBe(false);
  });

  it("submits strict multipart revision metadata without browser-owned integrity fields", async () => {
    const base = controlledDocumentWorkspaceFixture();
    const currentRevision = base.revisions[0];
    const currentFile = currentRevision?.files[0];
    if (!currentRevision || !currentFile)
      throw new Error("The revision fixture is unavailable.");
    const workspace: ControlledDocumentWorkspaceViewModel = {
      ...base,
      document: {
        ...base.document,
        optimisticVersion: 4,
      },
      revisions: [
        {
          ...currentRevision,
          files: [
            {
              ...currentFile,
              fileName: "replacement.pdf",
              sizeBytes: 4,
              scanState: "pending",
              scanObservedAt: null,
              capabilities: {
                ...currentFile.capabilities,
                integrity: {
                  state: "blocked",
                  reasonCode: "scan_pending",
                },
                preview: {
                  state: "blocked",
                  reasonCode: "scan_pending",
                  mode: "none",
                },
                download: {
                  state: "blocked",
                  reasonCode: "scan_pending",
                },
              },
            },
          ],
        },
      ],
    };
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(workspace as T));
    const source = new LiveDocumentDataSource(http);
    const file = new File(["%PDF"], "replacement.pdf", {
      type: "application/pdf",
    });

    await source.createRevision(
      documentProjectId,
      controlledDocumentId,
      {
        expectedDocumentVersion: 3,
        expectedLockVersion: 1,
        major: 0,
        minor: 1,
        reason: "  Controlled replacement  ",
        effectiveDate: "2026-07-30",
        predecessorRevisionId: null,
        file,
      },
      commandContext(),
    );

    const form = request.mock.calls[0]?.[1]?.body;
    expect(form).toBeInstanceOf(FormData);
    const metadataPart = (form as FormData).get("metadata");
    if (typeof metadataPart !== "string")
      throw new Error("The revision metadata part was not JSON text.");
    const metadata: unknown = JSON.parse(metadataPart);
    expect(metadata).toEqual({
      expectedDocumentVersion: 3,
      expectedLockVersion: 1,
      major: 0,
      minor: 1,
      reason: "Controlled replacement",
      effectiveDate: "2026-07-30",
      predecessorRevisionId: null,
    });
    expect(metadata).not.toHaveProperty("sha256");
    expect(metadata).not.toHaveProperty("scanState");
    const uploadedFile = (form as FormData).get("file");
    expect(uploadedFile).toBeInstanceOf(File);
    expect(uploadedFile).toMatchObject({
      name: file.name,
      size: file.size,
      type: file.type,
    });
  });

  it("validates audited content headers and returns exact bytes without a URL", async () => {
    const workspace = controlledDocumentWorkspaceFixture();
    const file = workspace.revisions[0]?.files[0];
    if (!file) throw new Error("The document file fixture is unavailable.");
    const fetch = vi.fn((_url: string | URL | Request, init?: RequestInit) => {
      const requestHeaders = new Headers(init?.headers);
      return Promise.resolve(
        new Response("%PDF", {
          status: 200,
          headers: {
            "Cache-Control": "private, no-store",
            "Content-Disposition":
              "inline; filename=\"synthetic-drawing.pdf\"; filename*=UTF-8''synthetic-drawing.pdf",
            "Content-Length": "4",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Content-Type": "application/pdf",
            "Idempotency-Replayed": "false",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Request-ID": requestHeaders.get("X-Request-ID") ?? "",
            "X-Trace-ID": "trace-document-content",
          },
        }),
      );
    });
    vi.stubGlobal("fetch", fetch);

    await expect(
      new LiveDocumentDataSource().loadContent(
        documentProjectId,
        controlledDocumentId,
        documentRevisionId,
        workspace.document.optimisticVersion,
        file,
        "inline",
        commandContext(),
      ),
    ).resolves.toMatchObject({
      size: 4,
      type: "application/pdf",
    });
    const [url, init] = fetch.mock.calls[0] ?? [];
    expect(url).toBe(
      `/api/npi/v1/projects/${documentProjectId}/documents/${controlledDocumentId}/revisions/${documentRevisionId}/files/${fileRevisionId}:content`,
    );
    const body = init?.body;
    if (typeof body !== "string")
      throw new Error("The content command body was not JSON.");
    const parsedBody: unknown = JSON.parse(body);
    expect(parsedBody).toEqual({
      expectedDocumentVersion: workspace.document.optimisticVersion,
      expectedFileVersion: file.optimisticVersion,
      disposition: "inline",
    });
    expect(new Headers(init?.headers).get("Accept")).toBe("application/pdf");
  });

  it("fails closed when an audited content security header is absent", async () => {
    const workspace = controlledDocumentWorkspaceFixture();
    const file = workspace.revisions[0]?.files[0];
    if (!file) throw new Error("The document file fixture is unavailable.");
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string | URL | Request, init?: RequestInit) => {
        return Promise.resolve(
          new Response("%PDF", {
            status: 200,
            headers: {
              "Cache-Control": "private, no-store",
              "Content-Disposition":
                "attachment; filename=\"synthetic-drawing.pdf\"; filename*=UTF-8''synthetic-drawing.pdf",
              "Content-Length": "4",
              "Content-Security-Policy": "sandbox; default-src 'none'",
              "Content-Type": "application/pdf",
              "Idempotency-Replayed": "false",
              "X-Request-ID":
                new Headers(init?.headers).get("X-Request-ID") ?? "",
              "X-Trace-ID": "trace-document-content",
              "X-Content-Type-Options": "nosniff",
            },
          }),
        );
      }),
    );

    await expect(
      new LiveDocumentDataSource().loadContent(
        documentProjectId,
        controlledDocumentId,
        documentRevisionId,
        workspace.document.optimisticVersion,
        file,
        "attachment",
        commandContext(),
      ),
    ).rejects.toMatchObject({ kind: "invalid_response" });
  });

  it("converts an aborted live request into a cancellation result", async () => {
    const http = new NpiHttpClient();
    vi.spyOn(http, "request").mockImplementation(
      <T>(_path: string, init: RequestInit = {}): Promise<T> =>
        new Promise<T>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            reject(
              new NpiTransportError("network", "request-aborted", "request"),
            );
          });
        }),
    );
    const controller = new AbortController();
    const request = new LiveDocumentDataSource(http).loadDocument(
      documentProjectId,
      controlledDocumentId,
      controller.signal,
    );

    controller.abort();
    await expect(request).rejects.toBeInstanceOf(DocumentRequestCancelledError);
  });

  it("rejects invalid lock and command context inputs before a request", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveDocumentDataSource(http);

    await expect(
      source.checkIn(
        documentProjectId,
        controlledDocumentId,
        3,
        0,
        commandContext(),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.recoverLock(
        documentProjectId,
        controlledDocumentId,
        3,
        1,
        " ",
        commandContext(),
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.checkOut(documentProjectId, controlledDocumentId, 3, {
        ...commandContext(),
        idempotencyKey: "short",
      }),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
  });
});
