export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail?: string;
  code?: string;
  traceId: string;
  retryable?: boolean;
  fieldErrors?: readonly Readonly<{ path: string; message: string }>[];
}

export type RequestFailureReference = "trace" | "request" | "client";
export type TransportFailureKind =
  | "network"
  | "invalid_response"
  | "request_not_ready";

export interface RequestFailure {
  kind: "problem" | TransportFailureKind | "unexpected";
  problem?: ProblemDetails;
  referenceId: string;
  referenceKind: RequestFailureReference;
}

export class NpiApiError extends Error {
  constructor(readonly problem: ProblemDetails) {
    super(problem.title);
    this.name = "NpiApiError";
  }
}

export class NpiTransportError extends Error {
  constructor(
    readonly kind: TransportFailureKind,
    readonly referenceId: string,
    readonly referenceKind: RequestFailureReference,
    options?: ErrorOptions,
  ) {
    super(
      kind === "network"
        ? "The NPI API request could not reach the server."
        : kind === "invalid_response"
          ? "The NPI API returned an invalid response."
          : "The NPI API request could not be prepared safely.",
      options,
    );
    this.name = "NpiTransportError";
  }
}

function createClientReference(prefix: "request" | "client"): string {
  return `${prefix}-${globalThis.crypto.randomUUID()}`;
}

function isProblemDetails(
  value: unknown,
  responseStatus: number,
  responseTraceId: string | null,
): value is ProblemDetails {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ProblemDetails>;
  const isFieldError = (fieldError: unknown): boolean => {
    if (!fieldError || typeof fieldError !== "object") return false;
    const record = fieldError as Record<string, unknown>;
    return (
      typeof record.path === "string" && typeof record.message === "string"
    );
  };
  const fieldErrorsAreValid =
    candidate.fieldErrors === undefined ||
    (Array.isArray(candidate.fieldErrors) &&
      (candidate.fieldErrors as readonly unknown[]).every(isFieldError));
  return (
    typeof candidate.type === "string" &&
    typeof candidate.title === "string" &&
    candidate.title.length > 0 &&
    typeof candidate.status === "number" &&
    Number.isInteger(candidate.status) &&
    candidate.status === responseStatus &&
    typeof candidate.traceId === "string" &&
    candidate.traceId.length > 0 &&
    (!responseTraceId || candidate.traceId === responseTraceId) &&
    (candidate.detail === undefined || typeof candidate.detail === "string") &&
    (candidate.code === undefined || typeof candidate.code === "string") &&
    (candidate.retryable === undefined ||
      typeof candidate.retryable === "boolean") &&
    fieldErrorsAreValid
  );
}

export function toRequestFailure(error: unknown): RequestFailure {
  if (error instanceof NpiApiError) {
    return {
      kind: "problem",
      problem: error.problem,
      referenceId: error.problem.traceId,
      referenceKind: "trace",
    };
  }
  if (error instanceof NpiTransportError) {
    return {
      kind: error.kind,
      referenceId: error.referenceId,
      referenceKind: error.referenceKind,
    };
  }
  return {
    kind: "unexpected",
    referenceId: createClientReference("client"),
    referenceKind: "client",
  };
}

interface RequestOptions<T> {
  csrfToken?: string | undefined;
  validate?: ((value: unknown) => value is T) | undefined;
}

const safeMethods = new Set(["GET", "HEAD", "OPTIONS"]);
const bffPathPattern = /^\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*$/u;

export class NpiHttpClient {
  private readonly baseUrl = "/api/npi/v1";

  async request<T>(
    path: string,
    init: RequestInit = {},
    options: RequestOptions<T> = {},
  ): Promise<T> {
    if (!bffPathPattern.test(path))
      throw new Error(
        "NPI API paths must stay within the normalized BFF boundary.",
      );
    const method = (init.method ?? "GET").toUpperCase();
    const headers = new Headers(init.headers);
    if (!headers.has("Content-Type"))
      headers.set("Content-Type", "application/json");
    headers.set("Accept", "application/json, application/problem+json");
    headers.delete("X-Frappe-CSRF-Token");
    const requestId =
      headers.get("X-Trace-ID") ?? createClientReference("request");
    headers.set("X-Trace-ID", requestId);
    if (!safeMethods.has(method)) {
      if (!options.csrfToken) {
        throw new NpiTransportError(
          "request_not_ready",
          createClientReference("client"),
          "client",
        );
      }
      headers.set("X-Frappe-CSRF-Token", options.csrfToken);
    }
    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        credentials: "same-origin",
        headers,
      });
    } catch (error) {
      throw new NpiTransportError("network", requestId, "request", {
        cause: error,
      });
    }
    const responseTraceId = response.headers.get("X-Trace-ID");
    let body: unknown;
    try {
      body = await response.json();
    } catch (error) {
      throw new NpiTransportError(
        "invalid_response",
        responseTraceId ?? requestId,
        responseTraceId ? "trace" : "request",
        { cause: error },
      );
    }
    if (!response.ok) {
      if (isProblemDetails(body, response.status, responseTraceId))
        throw new NpiApiError(body);
      throw new NpiTransportError(
        "invalid_response",
        responseTraceId ?? requestId,
        responseTraceId ? "trace" : "request",
      );
    }
    let responseIsValid = true;
    try {
      responseIsValid = options.validate?.(body) ?? true;
    } catch {
      responseIsValid = false;
    }
    if (!responseIsValid) {
      throw new NpiTransportError(
        "invalid_response",
        responseTraceId ?? requestId,
        responseTraceId ? "trace" : "request",
      );
    }
    return body as T;
  }
}
