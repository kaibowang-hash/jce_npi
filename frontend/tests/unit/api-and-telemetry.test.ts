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
    expect(new Headers(request?.headers).get("X-Trace-ID")).toMatch(
      /^request-/,
    );
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
    expect((failure as NpiTransportError).referenceId).toMatch(/^request-/);
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
    expect(request).toHaveBeenNthCalledWith(
      1,
      "/session/bootstrap",
      {},
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
    expect(request).toHaveBeenCalledWith(
      "/session/bootstrap",
      {},
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
      } as UsabilityEvent);
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
