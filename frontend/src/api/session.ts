import type { Locale } from "../i18n/runtime";
import { NpiHttpClient } from "./http";

export interface SessionBootstrap {
  userId: string;
  language: Locale;
  allowedLanguages: readonly Locale[];
  csrfToken: string;
  catalog: {
    language: Locale;
    version: string;
    messages: Readonly<Record<string, string>>;
  };
}

export type SessionBootstrapValidator = (
  value: unknown,
) => value is SessionBootstrap;

export class SessionClient {
  private csrfToken: string | null = null;

  constructor(private readonly http = new NpiHttpClient()) {}

  clearSession(): void {
    this.csrfToken = null;
  }

  async getBootstrap(
    validate: SessionBootstrapValidator,
  ): Promise<SessionBootstrap> {
    const bootstrap = await this.http.request<SessionBootstrap>(
      "/session/bootstrap",
      {},
      { validate },
    );
    this.csrfToken = bootstrap.csrfToken;
    return bootstrap;
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

  async refreshAndSetLanguage(
    language: Locale,
    validateBootstrap: SessionBootstrapValidator,
    validateLanguage: SessionBootstrapValidator,
  ): Promise<SessionBootstrap> {
    const bootstrap = await this.getBootstrap(validateBootstrap);
    if (bootstrap.language === language) return bootstrap;
    return this.setLanguage(language, validateLanguage);
  }
}
