# Phase 3 Local Frappe Runtime Evidence

Validated on 2026-07-22 against the disposable `npi.localhost` Site. The
verification was restricted to loopback HTTP. No ERPNext instance, production
host, production credential, or production database was connected.

## Site and migration result

- Frappe: 15.115.4 at exact commit
  `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`.
- `make frappe-site-init`: **PASS**. The command installed/migrated `npi_core`
  before `npi_integration`, synchronized the custom DocTypes, ran migration
  hooks, and invalidated caches without a duplicate-install or destructive
  migration failure.
- The local service recovery retained the disposable development data volumes;
  no guarded volume reset was run.
- Site initialization uses Frappe v15 runtime CSV loading plus `clear-cache`.
  It intentionally does not run `bench build-message-files`, because that
  command rebuilds and can overwrite independently reviewed App source CSVs.

## Normal-user BFF proof

`make frappe-runtime-verify` started a temporary local Frappe process and
exercised only the `/api/npi/v1` boundary. The verifier returned:

```json
{"administratorLanguage":"en","administratorLanguageUnchanged":true,"catalogEntriesPerLocale":556,"csrfMissing":403,"csrfWrong":403,"disposableUserDeleted":true,"disposableUserId":"npi-runtime-user@example.invalid","disposableUserType":"Website User","extraField":422,"guest":401,"invalidLanguage":422,"languages":["en","zh","zh-TW"],"malformedJson":400,"missingLanguage":422,"unknownRoute":404,"wrongTypeLanguage":422}
```

The test created the exact disposable user
`npi-runtime-user@example.invalid` through the local Administrator REST
session only after proving that the user did not already exist. It then proved:

- the account is a normal `Website User`, has no `System Manager` role, and
  does not depend on Frappe Desk;
- the initial language is `en`;
- selecting `zh` persists to a fresh authenticated session;
- unsupported `zh-CN` returns HTTP 422 with a `language` field error and does
  not change the persisted selection;
- selecting `zh-TW` persists to another fresh authenticated session;
- a separate fresh Administrator session remains `en`, so the normal user's
  preference change does not leak to the Administrator;
- `en`, `zh`, and `zh-TW` each receive a catalog with exactly 556 messages and
  a 64-character SHA-256 version; both Chinese catalogs are independently
  complete direct CSV sources;
- anonymous bootstrap returns HTTP 401 and an unknown NPI route returns HTTP
  404;
- successful bootstrap and language-update responses contain exactly
  `userId`, `language`, `allowedLanguages`, `csrfToken`, and `catalog`, with no
  raw Frappe response envelope;
- each successful session response uses `Cache-Control: private, no-store`,
  carries `X-Trace-ID`, and exposes a bounded session CSRF token;
- a missing or wrong `X-Frappe-CSRF-Token` on the language `PUT` returns the
  retryable `CSRF_TOKEN_INVALID` Problem Details response as HTTP 403;
- malformed JSON returns `MALFORMED_REQUEST` as HTTP 400;
- an empty body, an additional request field, a wrong-type language, and an
  unapproved bootstrap query field return controlled field/validation errors
  as HTTP 422;
- every Problem Details response uses `application/problem+json`, carries the
  same trace identifier in the body and `X-Trace-ID`, preserves a valid
  caller-supplied trace identifier, and does not leak a Frappe exception
  envelope;
- every rejected mutation leaves the user's previous language unchanged; and
- cleanup deletes the exact disposable user and confirms a subsequent HTTP
  404.

The generated frontend catalog representing the same 556-key direct catalogs
has version `12e5adf665b2cd30`. The runtime BFF deliberately publishes a full
64-character SHA-256 catalog version instead of that shortened build-time
identifier.

The aggregate Python gate also covers a failure that the healthy loopback run
cannot induce safely: if user-cache invalidation raises after `User.save()`,
the request returns a retryable safe 500, rolls back the database transaction,
restores the in-memory language, and leaves both current-request locale fields
unchanged. This is unit-level transaction evidence, not a claim that the local
Redis service failed during the runtime verifier.

## Reproduction and cleanup

Run from the repository root:

```text
make start
make frappe-site-init
make frappe-runtime-verify
```

The verifier accepts the local Administrator password through
`NPI_ADMINISTRATOR_PASSWORD` and does not print it. Stop local services with
`make stop`. Before business data exists, rollback is to uninstall
`npi_integration` before `npi_core`, or remove only the disposable local Site.
The guarded volume reset must not be used unless local test data is
intentionally being discarded.

## Evidence boundary

This is local evidence for app installation/migration, authenticated BFF error
contracts, CSRF enforcement, Frappe user-language persistence, direct catalog
delivery, session isolation, and exact fixture cleanup. It does not prove
production topology, production identity integration, formal business
permissions, live Project or Tooling APIs, ERPNext connectivity,
notifications, or representative business data. Those claims require their
later phase environments and evidence.
