export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  code: string;
  traceId: string;
  retryable: boolean;
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

function createClientReference(prefix: "trace" | "client"): string {
  return `${prefix}-${globalThis.crypto.randomUUID()}`;
}

const uriReferencePattern =
  /^(?:[A-Za-z0-9\-._~:/?#[\]@!$&'()*+,;=]|%[0-9A-Fa-f]{2})+$/u;

function isUriReference(value: unknown): value is string {
  if (
    typeof value !== "string" ||
    value.length < 1 ||
    value.length > 2048 ||
    !uriReferencePattern.test(value)
  )
    return false;
  try {
    new URL(value, "https://npi.invalid/");
    return true;
  } catch {
    return false;
  }
}

function isProblemDetails(
  value: unknown,
  responseStatus: number,
  responseTraceId: string | null,
): value is ProblemDetails {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  const requiredKeys = [
    "type",
    "title",
    "status",
    "code",
    "traceId",
    "retryable",
  ] as const;
  const allowedKeys = new Set([
    ...requiredKeys,
    "detail",
    "instance",
    "fieldErrors",
  ]);
  if (
    !requiredKeys.every((key) =>
      Object.prototype.hasOwnProperty.call(candidate, key),
    ) ||
    !Object.keys(candidate).every((key) => allowedKeys.has(key))
  )
    return false;
  const boundedString = (
    candidateValue: unknown,
    minimum: number,
    maximum: number,
  ): candidateValue is string =>
    typeof candidateValue === "string" &&
    candidateValue.length >= minimum &&
    candidateValue.length <= maximum;
  const isFieldError = (fieldError: unknown): boolean => {
    if (!fieldError || typeof fieldError !== "object") return false;
    const record = fieldError as Record<string, unknown>;
    return (
      Object.keys(record).length === 2 &&
      Object.prototype.hasOwnProperty.call(record, "path") &&
      Object.prototype.hasOwnProperty.call(record, "message") &&
      boundedString(record.path, 1, 500) &&
      boundedString(record.message, 1, 1000)
    );
  };
  const fieldErrorsAreValid =
    candidate.fieldErrors === undefined ||
    (Array.isArray(candidate.fieldErrors) &&
      candidate.fieldErrors.length <= 100 &&
      candidate.fieldErrors.every(isFieldError));
  return (
    isUriReference(candidate.type) &&
    boundedString(candidate.title, 1, 280) &&
    typeof candidate.status === "number" &&
    Number.isInteger(candidate.status) &&
    candidate.status >= 400 &&
    candidate.status <= 599 &&
    candidate.status === responseStatus &&
    boundedString(candidate.code, 3, 100) &&
    /^[A-Z][A-Z0-9_]*$/u.test(candidate.code) &&
    boundedString(candidate.traceId, 8, 128) &&
    /^[A-Za-z0-9._:-]+$/u.test(candidate.traceId) &&
    (!responseTraceId || candidate.traceId === responseTraceId) &&
    (candidate.detail === undefined ||
      boundedString(candidate.detail, 0, 4000)) &&
    (candidate.instance === undefined || isUriReference(candidate.instance)) &&
    typeof candidate.retryable === "boolean" &&
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
  query?: Readonly<Record<string, string>> | undefined;
  requireIdempotencyReplay?: boolean | undefined;
  requirePrivateNoStore?: boolean | undefined;
  requireRequestIdEcho?: boolean | undefined;
  requireTraceId?: boolean | undefined;
  validate?: ((value: unknown) => value is T) | undefined;
}

const safeMethods = new Set(["GET", "HEAD", "OPTIONS"]);
const bffPathPattern =
  /^\/[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*(?::[a-z][a-z0-9-]*)?$/u;
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const traceIdPattern = /^[A-Za-z0-9._:-]{8,128}$/u;

export class NpiHttpClient {
  private readonly baseUrl = "/api/npi/v1";

  async request<T>(
    path: string,
    init: RequestInit = {},
    options: RequestOptions<T> = {},
  ): Promise<T> {
    const pathSegments = path.split("/").slice(1);
    if (
      !bffPathPattern.test(path) ||
      pathSegments.some((segment) => segment === "." || segment === "..")
    )
      throw new Error(
        "NPI API paths must stay within the normalized BFF boundary.",
      );
    const method = (init.method ?? "GET").toUpperCase();
    const headers = new Headers(init.headers);
    if (!headers.has("Content-Type"))
      headers.set("Content-Type", "application/json");
    headers.set("Accept", "application/json, application/problem+json");
    headers.delete("X-Frappe-CSRF-Token");
    const suppliedRequestId = headers.get("X-Request-ID");
    if (suppliedRequestId && !requestIdPattern.test(suppliedRequestId)) {
      throw new NpiTransportError(
        "request_not_ready",
        createClientReference("client"),
        "client",
      );
    }
    const requestId = suppliedRequestId ?? globalThis.crypto.randomUUID();
    headers.set("X-Request-ID", requestId);
    headers.set(
      "X-Trace-ID",
      headers.get("X-Trace-ID") ?? createClientReference("trace"),
    );
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
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(options.query ?? {}).sort(
        ([left], [right]) => left.localeCompare(right),
      )) {
        query.set(key, value);
      }
      const queryString = query.toString();
      response = await fetch(
        `${this.baseUrl}${path}${queryString ? `?${queryString}` : ""}`,
        {
          ...init,
          credentials: "same-origin",
          headers,
        },
      );
    } catch (error) {
      throw new NpiTransportError("network", requestId, "request", {
        cause: error,
      });
    }
    const responseTraceIdHeader = response.headers.get("X-Trace-ID");
    const responseTraceId =
      responseTraceIdHeader && traceIdPattern.test(responseTraceIdHeader)
        ? responseTraceIdHeader
        : null;
    const responseRequestId = response.headers.get("X-Request-ID");
    const idempotencyReplay = response.headers.get("Idempotency-Replayed");
    const cacheControl = response.headers.get("Cache-Control");
    const cacheControlDirectives = new Set(
      (cacheControl ?? "")
        .split(",")
        .map((directive) => directive.trim().toLowerCase())
        .filter(Boolean),
    );
    const privateNoStoreIsValid =
      cacheControlDirectives.size === 2 &&
      cacheControlDirectives.has("private") &&
      cacheControlDirectives.has("no-store");
    if (
      (options.requireTraceId && !responseTraceId) ||
      (options.requireRequestIdEcho && !responseRequestId) ||
      (responseRequestId !== null && responseRequestId !== requestId) ||
      (response.ok &&
        options.requirePrivateNoStore &&
        !privateNoStoreIsValid) ||
      (response.ok &&
        options.requireIdempotencyReplay &&
        idempotencyReplay !== "true" &&
        idempotencyReplay !== "false")
    ) {
      throw new NpiTransportError(
        "invalid_response",
        responseTraceId ?? requestId,
        responseTraceId ? "trace" : "request",
      );
    }
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
    let responseIsValid: boolean;
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
