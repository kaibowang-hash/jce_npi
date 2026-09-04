import type { Locale } from "../i18n/runtime";
import { NpiHttpClient } from "./http";

export type DeploymentEnvironment = "production" | "sandbox";

export interface SessionBootstrap {
  userId: string;
  isSystemManager?: boolean;
  deploymentEnvironment?: DeploymentEnvironment;
  language: Locale;
  allowedLanguages: readonly Locale[];
  csrfToken: string;
  preferences: {
    navigationCollapsed: boolean;
  };
  catalog: {
    language: Locale;
    version: string;
    messages: Readonly<Record<string, string>>;
  };
}

export type SessionBootstrapValidator = (
  value: unknown,
) => value is SessionBootstrap;

interface SessionLogout {
  signedOut: true;
}

export const sessionBootstrapTimeoutMilliseconds = 15_000;

function isSessionLogout(value: unknown): value is SessionLogout {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  return Object.keys(candidate).length === 1 && candidate.signedOut === true;
}

function abortError(signal: AbortSignal): Error {
  return signal.reason instanceof Error
    ? signal.reason
    : new DOMException(
        "The session bootstrap request was cancelled.",
        "AbortError",
      );
}

export class SessionClient {
  private csrfToken: string | null = null;
  private bootstrapAbortController: AbortController | null = null;

  constructor(
    private readonly http = new NpiHttpClient(),
    private readonly bootstrapTimeoutMilliseconds = sessionBootstrapTimeoutMilliseconds,
  ) {
    if (
      !Number.isFinite(bootstrapTimeoutMilliseconds) ||
      bootstrapTimeoutMilliseconds <= 0
    ) {
      throw new Error("The session bootstrap timeout must be positive.");
    }
  }

  clearSession(): void {
    this.csrfToken = null;
  }

  cancelPendingBootstrap(): void {
    const controller = this.bootstrapAbortController;
    this.bootstrapAbortController = null;
    controller?.abort(
      new DOMException(
        "The session bootstrap request was cancelled.",
        "AbortError",
      ),
    );
  }

  async getBootstrap(
    validate: SessionBootstrapValidator,
  ): Promise<SessionBootstrap> {
    this.cancelPendingBootstrap();
    const controller = new AbortController();
    this.bootstrapAbortController = controller;
    let removeAbortListener = (): void => undefined;
    const cancellation = new Promise<never>((_resolve, reject) => {
      const handleAbort = (): void => {
        reject(abortError(controller.signal));
      };
      controller.signal.addEventListener("abort", handleAbort, { once: true });
      removeAbortListener = () => {
        controller.signal.removeEventListener("abort", handleAbort);
      };
    });
    const timeout = globalThis.setTimeout(() => {
      controller.abort(
        new DOMException(
          "The session bootstrap request timed out.",
          "TimeoutError",
        ),
      );
    }, this.bootstrapTimeoutMilliseconds);
    try {
      const bootstrap = await Promise.race([
        this.http.request<SessionBootstrap>(
          "/session/bootstrap",
          { signal: controller.signal },
          { validate },
        ),
        cancellation,
      ]);
      this.csrfToken = bootstrap.csrfToken;
      return bootstrap;
    } finally {
      globalThis.clearTimeout(timeout);
      removeAbortListener();
      if (this.bootstrapAbortController === controller) {
        this.bootstrapAbortController = null;
      }
    }
  }

  async setLanguage(
    language: Locale,
    validate: SessionBootstrapValidator,
  ): Promise<SessionBootstrap> {
    const bootstrap = await this.http.request<SessionBootstrap>(
      "/session/language",
      {
        method: "PUT",
        body: JSON.stringify({ language }),
      },
      {
        csrfToken: this.csrfToken ?? undefined,
        validate,
      },
    );
    this.csrfToken = bootstrap.csrfToken;
    return bootstrap;
  }

  async setNavigationCollapsed(
    collapsed: boolean,
    validate: SessionBootstrapValidator,
  ): Promise<SessionBootstrap> {
    const bootstrap = await this.http.request<SessionBootstrap>(
      "/session/preferences/navigation",
      {
        method: "PUT",
        body: JSON.stringify({ collapsed }),
      },
      {
        csrfToken: this.csrfToken ?? undefined,
        validate,
      },
    );
    this.csrfToken = bootstrap.csrfToken;
    return bootstrap;
  }

  async signOut(): Promise<void> {
    try {
      await this.http.request<SessionLogout>(
        "/session/logout",
        {
          body: JSON.stringify({}),
          method: "POST",
          signal: AbortSignal.timeout(this.bootstrapTimeoutMilliseconds),
        },
        {
          csrfToken: this.csrfToken ?? undefined,
          requirePrivateNoStore: true,
          validate: isSessionLogout,
        },
      );
    } finally {
      // Any lost response can be timeout-after-commit. Require a fresh
      // bootstrap before this client is allowed to issue another command.
      this.clearSession();
    }
  }

  async refreshAndSetLanguage(
    language: Locale,
    validateBootstrap: SessionBootstrapValidator,
    validateLanguage: SessionBootstrapValidator,
  ): Promise<SessionBootstrap> {
    const bootstrap = await this.getBootstrap(validateBootstrap);
    if (bootstrap.language === language) return bootstrap;
    return this.setLanguage(language, validateLanguage);
  }

  async refreshAndSetNavigationCollapsed(
    collapsed: boolean,
    validateBootstrap: SessionBootstrapValidator,
    validatePreference: SessionBootstrapValidator,
  ): Promise<SessionBootstrap> {
    const bootstrap = await this.getBootstrap(validateBootstrap);
    if (bootstrap.preferences.navigationCollapsed === collapsed) {
      return bootstrap;
    }
    return this.setNavigationCollapsed(collapsed, validatePreference);
  }
}
