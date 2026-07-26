import { describe, expect, it, vi } from "vitest";

import {
  NpiApiError,
  NpiHttpClient,
  NpiTransportError,
} from "../../src/api/http";
import { SessionClient, type SessionBootstrap } from "../../src/api/session";
import {
  UsabilityRecorder,
  validateUsabilityEvent,
  type UsabilityEvent,
} from "../../src/telemetry/recorder";

const event: UsabilityEvent = {
  name: "route_viewed",
  route: "/project",
  outcome: "viewed",
  durationMs: 42,
  contextSwitches: 1,
  occurredAt: "2026-07-21T14:32:00Z",
};

function acceptBootstrapFixture(value: unknown): value is SessionBootstrap {
  return Boolean(value && typeof value === "object");
}

describe("NPI BFF client boundary", () => {
  it("rejects paths outside its absolute application boundary", async () => {
    await expect(new NpiHttpClient().request("api/resource")).rejects.toThrow(
      "NPI API paths must stay within the normalized BFF boundary.",
    );
  });

  it.each([
    "//external.invalid/path",
    "/../../../api/method/admin",
    "/session/%2e%2e/admin",
    "/session/%252e%252e/admin",
    "/session/bootstrap?email=user@example.invalid",
    "/session/bootstrap#secret",
    "/session\\bootstrap",
  ])("rejects unsafe BFF path %s before fetch", async (path) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(new NpiHttpClient().request(path)).rejects.toThrow(
      "normalized BFF boundary",
    );
    expect(fetch).not.toHaveBeenCalled();
  });

  it("sends same-origin JSON requests only below /api/npi/v1", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ value: 7 }), { status: 200 }),
        ),
      ),
    );
    await expect(
      new NpiHttpClient().request<{ value: number }>("/fixture", {
        headers: { "X-Frappe-CSRF-Token": "must-not-leak-on-get" },
      }),
    ).resolves.toEqual({ value: 7 });
    expect(globalThis.fetch).toHaveBeenCalledOnce();
    const [url, request] = vi.mocked(globalThis.fetch).mock.calls[0] ?? [];
    expect(url).toBe("/api/npi/v1/fixture");
    expect(request).toEqual(
      expect.objectContaining({ credentials: "same-origin" }),
    );
    expect(new Headers(request?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(new Headers(request?.headers).get("X-Frappe-CSRF-Token")).toBeNull();
    expect(new Headers(request?.headers).get("X-Request-ID")).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u,
    );
    expect(new Headers(request?.headers).get("X-Trace-ID")).toMatch(/^trace-/);
  });

  it("encodes structured query options without weakening the normalized BFF path boundary", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ value: 7 }), { status: 200 }),
        ),
      ),
    );

    await new NpiHttpClient().request(
      "/projects/11111111-1111-4111-8111-111111111111/domain-work-items",
      {},
      {
        query: {
          ownerUserId: "quality.lead@example.invalid",
          cursor: "opaque+cursor/value",
        },
      },
    );

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0] ?? [];
    expect(url).toBe(
      "/api/npi/v1/projects/11111111-1111-4111-8111-111111111111/domain-work-items?cursor=opaque%2Bcursor%2Fvalue&ownerUserId=quality.lead%40example.invalid",
    );
  });

  it("preserves separate canonical request and trace identities", async () => {
    const requestId = "11111111-1111-4111-8111-111111111111";
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ value: 7 }), { status: 200 }),
        ),
      ),
    );

    await new NpiHttpClient().request("/fixture", {
      headers: {
        "X-Request-ID": requestId,
        "X-Trace-ID": "trace-caller-owned",
      },
    });
    const [, request] = vi.mocked(globalThis.fetch).mock.calls[0] ?? [];
    const headers = new Headers(request?.headers);
    expect(headers.get("X-Request-ID")).toBe(requestId);
    expect(headers.get("X-Trace-ID")).toBe("trace-caller-owned");
  });

  it("rejects a malformed caller request ID before fetch", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    await expect(
      new NpiHttpClient().request("/fixture", {
        headers: { "X-Request-ID": "request-not-a-uuid" },
      }),
    ).rejects.toMatchObject({
      kind: "request_not_ready",
      referenceKind: "client",
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("requires an exact response request-ID echo when the endpoint contract enables it", async () => {
    const requestId = "11111111-1111-4111-8111-111111111111";
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ value: 7 }), {
            status: 200,
            headers: { "X-Request-ID": requestId },
          }),
        ),
      ),
    );

    await expect(
      new NpiHttpClient().request(
        "/fixture",
        { headers: { "X-Request-ID": requestId } },
        { requireRequestIdEcho: true },
      ),
    ).resolves.toEqual({ value: 7 });

    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ value: 8 }), {
        status: 200,
        headers: {
          "X-Request-ID": "22222222-2222-4222-8222-222222222222",
          "X-Trace-ID": "trace-request-mismatch",
        },
      }),
    );
    const failure = await new NpiHttpClient()
      .request(
        "/fixture",
        { headers: { "X-Request-ID": requestId } },
        { requireRequestIdEcho: true },
      )
      .catch((error: unknown) => error);
    expect(failure).toMatchObject({
      kind: "invalid_response",
      referenceId: "trace-request-mismatch",
      referenceKind: "trace",
    });
  });

  it.each([undefined, "bad trace header"])(
    "rejects a required missing or malformed response trace %s",
    async (traceId) => {
      const requestId = "11111111-1111-4111-8111-111111111111";
      const headers: Record<string, string> = { "X-Request-ID": requestId };
      if (traceId) headers["X-Trace-ID"] = traceId;
      vi.stubGlobal(
        "fetch",
        vi.fn(() =>
          Promise.resolve(
            new Response(JSON.stringify({ value: 7 }), {
              status: 200,
              headers,
            }),
          ),
        ),
      );

      const failure = await new NpiHttpClient()
        .request(
          "/fixture",
          { headers: { "X-Request-ID": requestId } },
          { requireRequestIdEcho: true, requireTraceId: true },
        )
        .catch((error: unknown) => error);

      expect(failure).toMatchObject({
        kind: "invalid_response",
        referenceId: requestId,
        referenceKind: "request",
      });
    },
  );

  it("rejects a problem response when its required trace header is missing", async () => {
    const requestId = "11111111-1111-4111-8111-111111111111";
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              type: "urn:npi:error:validation",
              title: "The request failed validation.",
              status: 422,
              code: "VALIDATION_FAILED",
              traceId: "trace-body-only",
              retryable: false,
            }),
            {
              status: 422,
              headers: { "X-Request-ID": requestId },
            },
          ),
        ),
      ),
    );

    const failure = await new NpiHttpClient()
      .request(
        "/fixture",
        { headers: { "X-Request-ID": requestId } },
        { requireRequestIdEcho: true, requireTraceId: true },
      )
      .catch((error: unknown) => error);

    expect(failure).toMatchObject({
      kind: "invalid_response",
      referenceId: requestId,
      referenceKind: "request",
    });
  });

  it("fails closed before an unsafe request when no in-memory CSRF token is available", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const failure = await new NpiHttpClient()
      .request("/fixture", { method: "PUT" })
      .catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(NpiTransportError);
    expect((failure as NpiTransportError).kind).toBe("request_not_ready");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("adds the in-memory CSRF token only to unsafe same-origin requests", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ value: 7 }), { status: 200 }),
        ),
      ),
    );
    await new NpiHttpClient().request(
      "/fixture",
      { method: "PUT" },
      { csrfToken: "csrf-fixture" },
    );
    const [, request] = vi.mocked(globalThis.fetch).mock.calls[0] ?? [];
    expect(new Headers(request?.headers).get("X-Frappe-CSRF-Token")).toBe(
      "csrf-fixture",
    );
  });

  it("keeps a client request reference for a network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("secret"))),
    );
    const failure = await new NpiHttpClient()
      .request("/fixture")
      .catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(NpiTransportError);
    expect((failure as NpiTransportError).kind).toBe("network");
    expect((failure as NpiTransportError).referenceKind).toBe("request");
    expect((failure as NpiTransportError).referenceId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u,
    );
    expect((failure as Error).message).not.toContain("secret");
  });

  it("uses the server trace header when a response is not valid JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response("gateway failure", {
            status: 502,
            headers: { "X-Trace-ID": "trace-invalid-json" },
          }),
        ),
      ),
    );
    const failure = await new NpiHttpClient()
      .request("/fixture")
      .catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(NpiTransportError);
    expect((failure as NpiTransportError).kind).toBe("invalid_response");
    expect((failure as NpiTransportError).referenceId).toBe(
      "trace-invalid-json",
    );
    expect((failure as Error).message).not.toContain("gateway failure");
  });

  it("preserves localized problem details and trace identity", async () => {
    const problem = {
      type: "urn:npi:error:validation",
      title: "The request failed validation.",
      status: 422,
      code: "VALIDATION_FAILED",
      traceId: "trc-fixture",
      retryable: false,
      fieldErrors: [
        {
          path: "language",
          message: "Select a supported language.",
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify(problem), { status: 422 })),
      ),
    );
    const failure = await new NpiHttpClient()
      .request("/fixture")
      .catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(NpiApiError);
    expect((failure as NpiApiError).problem).toEqual(problem);
  });

  it.each([
    [
      "an unknown top-level field",
      {
        type: "urn:npi:error:validation",
        title: "The request failed validation.",
        status: 422,
        code: "VALIDATION_FAILED",
        traceId: "trace-closed-contract",
        retryable: false,
        untrustedDebugField: "secret",
      },
    ],
    [
      "a missing code",
      {
        type: "urn:npi:error:validation",
        title: "The request failed validation.",
        status: 422,
        traceId: "trace-closed-contract",
        retryable: false,
      },
    ],
    [
      "a missing retryable flag",
      {
        type: "urn:npi:error:validation",
        title: "The request failed validation.",
        status: 422,
        code: "VALIDATION_FAILED",
        traceId: "trace-closed-contract",
      },
    ],
    [
      "an unknown field-error property",
      {
        type: "urn:npi:error:validation",
        title: "The request failed validation.",
        status: 422,
        code: "VALIDATION_FAILED",
        traceId: "trace-closed-contract",
        retryable: false,
        fieldErrors: [
          { path: "title", message: "Enter a title.", raw: "secret" },
        ],
      },
    ],
    [
      "too many field errors",
      {
        type: "urn:npi:error:validation",
        title: "The request failed validation.",
        status: 422,
        code: "VALIDATION_FAILED",
        traceId: "trace-closed-contract",
        retryable: false,
        fieldErrors: Array.from({ length: 101 }, (_, index) => ({
          path: `field-${String(index)}`,
          message: "Enter a value.",
        })),
      },
    ],
    [
      "a malformed problem type URI",
      {
        type: "not a URI reference",
        title: "The request failed validation.",
        status: 422,
        code: "VALIDATION_FAILED",
        traceId: "trace-closed-contract",
        retryable: false,
      },
    ],
    [
      "a malformed instance URI",
      {
        type: "urn:npi:error:validation",
        title: "The request failed validation.",
        status: 422,
        code: "VALIDATION_FAILED",
        traceId: "trace-closed-contract",
        retryable: false,
        instance: "%ZZ",
      },
    ],
    [
      "an oversized problem type URI",
      {
        type: `urn:npi:error:${"x".repeat(2048)}`,
        title: "The request failed validation.",
        status: 422,
        code: "VALIDATION_FAILED",
        traceId: "trace-closed-contract",
        retryable: false,
      },
    ],
  ])("rejects ProblemDetails containing %s", async (_label, body) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(body), {
            status: 422,
            headers: { "X-Trace-ID": "trace-closed-contract" },
          }),
        ),
      ),
    );

    const failure = await new NpiHttpClient()
      .request("/fixture")
      .catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(NpiTransportError);
    expect((failure as NpiTransportError).kind).toBe("invalid_response");
    expect((failure as NpiTransportError).referenceId).toBe(
      "trace-closed-contract",
    );
  });

  it("converts a malformed problem body into a safe transport failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              type: "urn:npi:error:validation",
              title: "The request failed validation.",
              status: 422,
              traceId: "trace-body-mismatch",
              detail: { raw: "secret response content" },
              fieldErrors: "not-an-array",
            }),
            {
              status: 422,
              headers: { "X-Trace-ID": "trace-response-safe" },
            },
          ),
        ),
      ),
    );
    const failure = await new NpiHttpClient()
      .request("/fixture")
      .catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(NpiTransportError);
    expect((failure as NpiTransportError).kind).toBe("invalid_response");
    expect((failure as NpiTransportError).referenceId).toBe(
      "trace-response-safe",
    );
    expect((failure as Error).message).not.toContain("secret response content");
  });

  it("uses the session bootstrap and controlled language endpoints", async () => {
    const bootstrap = {
      allowedLanguages: ["en"] as const,
      catalog: { language: "en" as const, messages: {}, version: "v1" },
      csrfToken: "csrf-v1",
      language: "en" as const,
      userId: "phase3@example.invalid",
    };
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(bootstrap as T));
    const client = new SessionClient(http);
    await client.getBootstrap(acceptBootstrapFixture);
    await client.setLanguage("zh-TW", acceptBootstrapFixture);
    expect(request.mock.calls[0]?.[1]?.signal?.aborted).toBe(false);
    expect(request).toHaveBeenNthCalledWith(
      1,
      "/session/bootstrap",
      { signal: request.mock.calls[0]?.[1]?.signal },
      { validate: acceptBootstrapFixture },
    );
    expect(request).toHaveBeenNthCalledWith(
      2,
      "/session/language",
      expect.objectContaining({
        body: JSON.stringify({ language: "zh-TW" }),
        method: "PUT",
      }),
      { csrfToken: "csrf-v1", validate: acceptBootstrapFixture },
    );
  });

  it("removes the in-memory CSRF token when the session is cleared", async () => {
    const bootstrap = {
      allowedLanguages: ["en"] as const,
      catalog: { language: "en" as const, messages: {}, version: "v1" },
      csrfToken: "csrf-v1",
      language: "en" as const,
      userId: "phase3@example.invalid",
    };
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(bootstrap as T));
    const client = new SessionClient(http);

    await client.getBootstrap(acceptBootstrapFixture);
    client.clearSession();
    await client.setLanguage("zh", acceptBootstrapFixture);

    expect(request).toHaveBeenNthCalledWith(
      2,
      "/session/language",
      expect.objectContaining({
        body: JSON.stringify({ language: "zh" }),
        method: "PUT",
      }),
      { csrfToken: undefined, validate: acceptBootstrapFixture },
    );
  });

  it("reconciles an indeterminate language result before issuing a duplicate PUT", async () => {
    const bootstrap = {
      allowedLanguages: ["en", "zh", "zh-TW"] as const,
      catalog: {
        language: "zh" as const,
        messages: {},
        version: "a".repeat(64),
      },
      csrfToken: "a".repeat(32),
      language: "zh" as const,
      userId: "phase3@example.invalid",
    };
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockImplementation(<T>(): Promise<T> => Promise.resolve(bootstrap as T));
    const client = new SessionClient(http);

    await expect(
      client.refreshAndSetLanguage(
        "zh",
        acceptBootstrapFixture,
        acceptBootstrapFixture,
      ),
    ).resolves.toEqual(bootstrap);
    expect(request).toHaveBeenCalledOnce();
    expect(request.mock.calls[0]?.[1]?.signal?.aborted).toBe(false);
    expect(request).toHaveBeenCalledWith(
      "/session/bootstrap",
      { signal: request.mock.calls[0]?.[1]?.signal },
      { validate: acceptBootstrapFixture },
    );
  });
});

describe("privacy-safe usability telemetry", () => {
  it("accepts allowlisted aggregate metadata and records a frozen development copy", async () => {
    expect(() => {
      validateUsabilityEvent(event);
    }).not.toThrow();
    const recorder = new UsabilityRecorder();
    await recorder.record(event);
    expect(recorder.prototypeEvents).toEqual([event]);
    expect(Object.isFrozen(recorder.prototypeEvents[0])).toBe(true);
  });

  it("rejects sensitive fields, content-bearing routes, and invalid counters", () => {
    expect(() => {
      validateUsabilityEvent({
        ...event,
        bodyText: "secret",
      });
    }).toThrow("Sensitive telemetry field is forbidden: bodyText");
    for (const route of [
      "/projects/PJ-26018",
      "/?email=user@example.invalid",
      "/work#customer",
      "/%70rojects/PJ-26018",
      "/project/",
    ]) {
      expect(() => {
        validateUsabilityEvent({ ...event, route });
      }).toThrow("Telemetry route must be a normalized screen path.");
    }
    expect(() => {
      validateUsabilityEvent({ ...event, durationMs: -1 });
    }).toThrow("Telemetry duration must be a finite nonnegative number.");
    expect(() => {
      validateUsabilityEvent({ ...event, contextSwitches: -1 });
    }).toThrow("Telemetry context switches must be a nonnegative integer.");
  });

  it("accepts only canonical screen routes and constrained runtime values", () => {
    for (const route of [
      "/work",
      "/project",
      "/gate",
      "/tooling",
      "/trial",
      "/execution",
    ]) {
      expect(() => {
        validateUsabilityEvent({ ...event, route });
      }).not.toThrow();
    }
    expect(() => {
      validateUsabilityEvent({ ...event, name: "customer@example.invalid" });
    }).toThrow("Telemetry event name is not allowlisted.");
    expect(() => {
      validateUsabilityEvent({ ...event, outcome: "customer content" });
    }).toThrow("Telemetry outcome is not allowlisted.");
    expect(() => {
      validateUsabilityEvent({ ...event, occurredAt: "customer content" });
    }).toThrow("Telemetry timestamp must be a UTC ISO timestamp.");
    expect(() => {
      validateUsabilityEvent({
        ...event,
        durationMs: Number.POSITIVE_INFINITY,
      });
    }).toThrow("Telemetry duration must be a finite nonnegative number.");
    expect(() => {
      validateUsabilityEvent({ ...event, contextSwitches: 1.5 });
    }).toThrow("Telemetry context switches must be a nonnegative integer.");
  });
});
