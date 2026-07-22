# Phase 3 Gate — TECHNICAL_PASS_PENDING_UAT

Gate date: 2026-07-22

Controller phase: 3 — React App Shell, Siemens UI, and i18n foundation

Release-gate technical decision: **PASS**

Phase acceptance status: **TECHNICAL_PASS_PENDING_UAT**

Independent review returned the first Phase 3 gate candidate for bounded
formal-error, CSRF, telemetry-privacy, transaction, and request-locale
atomicity repairs. Repair round 1 is implemented, the complete aggregate,
runtime, browser, and visual evidence below was rerun, and the independent final
review returned `PASS` with no release-blocking findings. The checkpoint does not constitute business UAT,
production readiness, or acceptance of fixture data as representative
operational data. `FR-UX-031` remains pending named business reviewers and a
provenance-backed sanitized sample package, so the truthful phase status is
`TECHNICAL_PASS_PENDING_UAT` rather than an unqualified business `PASS`.

## 1. Scope and acceptance mapping

The checkpoint is limited to the Pack-defined Phase 3 boundary:

- the independent React 18 + TypeScript + Vite SPA and domain-first App Shell;
- the version-locked Siemens iX Classic Light implementation behind the local
  `frontend/src/ui-adapters/` boundary and company-owned design tokens;
- reusable engineering worklist, object-page, split-workspace, inspector,
  state, impact-review, provenance, and operation-status primitives;
- six explicitly labelled Project, Gate, Tooling, Trial, My Work, and ERP
  execution prototype paths, including deterministic non-normal states;
- English source strings plus complete Frappe-compatible `zh` and `zh-TW`
  catalogs, the React `t()` adapter, locale formatters/renderers, and the fixed
  `/api/npi/v1` session-localization BFF surface; and
- automated unit, browser, accessibility, localization, design-token,
  dependency, migration, runtime, and visual evidence.

`implementation/REQUIREMENT_TRACEABILITY.csv` contains 173 unique Pack
requirements. All 41 rows assigned to Phase 3 have implementation and test
evidence: 23 are `TECHNICAL_VERIFIED`, 14 are
`TECHNICAL_VERIFIED_PROTOTYPE`, three are
`TECHNICAL_VERIFIED_FOUNDATION`, and one (`FR-UX-031`) is
`PENDING_BUSINESS_UAT_AND_SANITIZED_DATA`. Prototype/foundation statuses are
intentional scope statements, not substitutes for later live capability.

This phase does **not** deliver persisted Project/Gate/Tooling/Trial business
logic, a live business ViewModel BFF, production Worklist paging, formal ERP
writes, production ERP connectivity, a notification service, durable telemetry,
or live mail/print/export delivery. It does not authorize production deployment
or expand Phase 3 into later controller phases.

## 2. Reproducible technical evidence

Detailed durable records are in
`implementation/evidence/phase-3/technical-test-results.md`,
`runtime-validation.md`, `dependency-review.md`, and `visual-review.md`.

| Command / review | Result | Exact evidence |
|---|---|---|
| `npm ci` in `frontend/` | **PASS** | 432 packages installed and 433 packages audited from the committed lockfile |
| `npm run verify` in `frontend/` | **PASS** | Generated-artifact checks, TypeScript, ESLint, Prettier, Stylelint, adapter/BFF boundaries, UI-token and i18n gates, 110/110 unit/component tests, coverage, production build, and both dependency audits passed |
| `npm run test:e2e -- --reporter=line` in `frontend/` | **PASS** | Final clean standalone run passed 63/63 non-visual Chromium tests in 2.6 minutes |
| `npm run test:visual:update` in `frontend/` | **PASS** | All 129 deterministic screenshots were force-regenerated with `--update-snapshots=all` under exact-zero-difference configuration in 4.3 minutes |
| `npm run test:visual` in `frontend/` | **PASS** | 129/129 screenshots matched the regenerated baseline with `maxDiffPixelRatio: 0` in 3.9 minutes; no update mode was used |
| `make frappe-site-init` | **PASS** | The disposable `npi.localhost` Site installed/migrated `npi_core` before `npi_integration` against Frappe 15.115.4 at `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` |
| `make frappe-runtime-verify` | **PASS** | Authenticated normal-user locale persistence, direct catalogs, error contracts, Administrator isolation, and exact fixture cleanup passed over loopback HTTP |
| `make verify` | **PASS** | 58/58 Python repository/API/security/localization tests and the complete frontend verification passed; JSON, compilation, trace uniqueness, prohibited-pattern, and diff checks passed |
| `git diff --check` | **PASS** | Exit 0; no whitespace error |

Frontend coverage is 4,319/4,646 statements and lines (92.96%), 784/863
branches (90.84%), and 144/160 functions (90.00%). The final standalone
production build transformed 390 modules and emitted a 761.17 kB minified /
190.88 kB gzip main JavaScript asset plus 225.79 kB minified / 22.86 kB gzip
CSS. Both `npm audit`
and `npm audit --omit=dev` reported zero known vulnerabilities. The unchanged
Vite warning for the main JavaScript asset above 500 kB is recorded performance
debt; its threshold was not weakened or hidden.

## 3. Local runtime, API contract, and permission evidence

`contracts/npi-api.openapi.yaml` now specifies only the live Phase 3 additions:
authenticated session bootstrap, controlled current-user language update,
`en`/`zh`/`zh-TW`, a versioned filtered catalog, and established problem
responses. Existing future business paths in the contract are not presented as
live Phase 3 endpoints. Integration-event schemas and data-ownership boundaries
are unchanged by this checkpoint.

The local runtime verifier created an exact disposable Website User, proved the
user was not a System Manager and did not require Desk, and returned:

```json
{"administratorLanguage":"en","administratorLanguageUnchanged":true,"catalogEntriesPerLocale":556,"csrfMissing":403,"csrfWrong":403,"disposableUserDeleted":true,"disposableUserId":"npi-runtime-user@example.invalid","disposableUserType":"Website User","extraField":422,"guest":401,"invalidLanguage":422,"languages":["en","zh","zh-TW"],"malformedJson":400,"missingLanguage":422,"unknownRoute":404,"wrongTypeLanguage":422}
```

The normal Website User persisted `zh` and then `zh-TW` across fresh
authenticated sessions. Unsupported `zh-CN` returned HTTP 422 without changing
the stored preference. Missing, wrongly typed, or extra language fields returned
HTTP 422; malformed JSON returned 400. Missing or invalid CSRF tokens returned
403 before mutation. A fresh Administrator session remained `en`. Each locale
received exactly 556 messages and a 64-character SHA-256 catalog version; both
Chinese catalogs were independently complete. Guest bootstrap returned 401,
an unknown NPI route returned 404, and problem responses used
`application/problem+json` plus `X-Trace-ID`. Cleanup deleted only the exact
disposable user and confirmed a subsequent 404.

The BFF maps a fixed `/api/npi/v1` route table and strips Frappe's RPC envelope.
Although Frappe entry points must permit routing before domain checks, the
handlers explicitly reject `Guest`; the loopback runtime proves that boundary.
The language update operates on the authenticated user's own Frappe User record
and preserves Frappe permission enforcement. No `ignore_permissions`, direct
SQL, browser-to-ERP call, cross-database access, core patch, dual-master field,
secret, test backdoor, or hard-coded production identifier was found. This is
session/localization permission evidence only; it does not claim that later
Project or Gate authorization is already live.

## 4. Migration and rollback

`make frappe-site-init` exercised the real pinned Frappe v15 install/migrate
path, including the corrected custom-App module layout, app installation order,
DocType synchronization, migration hooks, and cache invalidation. Re-running the
initializer is idempotent for the disposable Site. No ERPNext app, production
host, production credential, production database, destructive patch, or
cross-database migration was used.

The source rollback is checkpoint-scoped: revert the Phase 3 changes and
regenerate the frontend lock/build artifacts. Before business data exists, the
local Site rollback is to uninstall `npi_integration` before `npi_core`, or to
remove only the disposable `npi.localhost` Site. Named Compose volumes remain
preserved unless a user separately invokes the explicitly guarded destructive
reset. Any later environment containing retained data requires a reviewed
forward fix or an environment-specific backup/restore plan; this technical gate
does not authorize a production migration or rollback.

## 5. Localization gate

The implementation follows accepted ADR-005 and the pinned Frappe v15 facts:

- English literal source strings are the only authoring keys; React user copy
  is routed through the local `t()` adapter;
- runtime catalogs are headerless App CSV files for `zh` and `zh-TW`, with
  independent direct coverage so Frappe parent-language inheritance cannot hide
  missing Traditional Chinese rows;
- literal/context extraction, catalog coverage, duplicate, placeholder,
  controlled-terminology, retain-term, hard-coded-copy, and mixed-language
  checks passed;
- all three locales passed visible-text, relevant-attribute, and open-shadow-root
  scans in the browser matrix; and
- date, number, currency, percent, unit, list, notification, mail, print, and
  export copy infrastructure is exercised through shared formatter/renderer
  tests.

The last point is foundation evidence only. Browser time is fixed to UTC for
deterministic prototype evidence, and no live user/company timezone, notification
delivery, mail transport, print generator, or export pipeline is claimed.

## 6. Industrial UX, accessibility, and exact visual gate

The visual matrix contains 18 locale views, 30 desktop/zoom-equivalent geometry
views, 78 non-normal state views, and three field-tablet views. It covers six
core screens in English, Simplified Chinese, and Traditional Chinese; 1366x768
and 1920x1080 layouts; 125% and 150% zoom-equivalent cases; and loading, empty,
no-permission, read-only, partial, error, conflict, validation, queued,
processing, retryable-failure, final-failure, and dirty states.

The baseline was force-regenerated after the final UI changes and independently
compared at exact zero pixel-difference tolerance. Six representative files were
then reviewed at original resolution: English Project, Simplified Chinese
Tooling, Traditional Chinese ERP execution, the 1920x1080/150%-equivalent
Project geometry, a Simplified Chinese Gate error, and a Traditional Chinese
768x1024 Trial field view. The reviewed renders show the final zero-notification
state and catalog version prefix `12e5adf665b2cd30`, so the reviewed evidence is
the regenerated baseline rather than the earlier stale screenshots.

The combined automated and manual evidence confirms neutral surfaces, one
industrial-teal primary accent, 0-2 px ordinary geometry, tokenized one-pixel
boundaries, no panel shadow, no gradient/glass/decorative illustration, dense
tables/trees/split panes, a stable shell and docked inspector, one visual primary
action, and text/icon/shape status semantics. The 63-test browser suite also
passed keyboard and focus behavior, native iX accessible names/disclosure,
150%-equivalent layout, 390x844 field-phone interaction, and WCAG A/AA axe
checks. No Frappe Desk chrome or raw DocType flow appears in the normal-user
paths.

## 7. Diff, dependency, documentation, and trace review

The changed scope is consistent with the requirement anchor: frontend and test
configuration; React App Shell, local adapters, pages, fixtures, and tests;
token/catalog generation and verification; canonical Frappe catalogs and the
session-localization BFF; the local Site/runtime scripts; the OpenAPI and
terminology contract updates; approved ADR/runtime/dependency/UAT evidence; and
CI/Make wiring. The exact dependency versions, MIT licenses, public upstream
metadata, adapter-scoped rollback, alternatives, audit result, and bundle impact
are recorded in ADR-003 and `dependency-review.md`.

The requirement CSV remains 173/173 unique and maps every Phase 3 row to code
and test/evidence paths. The technical result, runtime proof, visual review,
unsigned UAT script, dependency decision, requirement anchor, localization
documentation, development runbook, and single external-input request are
aligned with the implementation. No accepted-path TODO/FIXME, silent failure,
fake success, skipped failing check, or unrecorded requirement expansion was
used to obtain the technical result.

## 8. Open acceptance items and known boundaries

The following items remain explicit and do not invalidate the technical PASS:

1. **Business UAT:** Project Management, Engineering/Tooling, and Quality must
   complete all six workflows in `en`, `zh`, and `zh-TW`, record duration,
   context switches and findings, sign the result, and close every Severe
   usability finding. Codex has not and will not sign for those reviewers.
2. **Representative data:** the six automated paths use labelled deterministic
   fixtures. The repository has no provenance-backed sanitized operational
   package for the two required project types, so fixtures are not represented
   as real-data acceptance.
3. **Live application services:** the Worklist uses a bounded fixture transport;
   production paging/scale, live business ViewModel APIs, notification counts,
   persisted activity, durable remote operations, and durable telemetry remain
   later-phase work. The 10,000-row bounded-DOM test is not a production
   performance claim.
4. **ERPNext:** the execution view is an honest contract-backed prototype. No
   live ERPNext connection, formal write, returned production identifier, or
   real ERP deep link was exercised. Production ERPNext remains prohibited.
5. **Non-screen and locale operating context:** mail/print/export/notification
   evidence is renderer-level, and UTC is a deterministic fixture setting rather
   than a proven live user/company timezone.
6. **Performance:** the measured main JavaScript bundle warning remains open and
   must be re-evaluated as live data access and later business modules are added.

`implementation/REQUIRED_INPUTS.md` is the single complete request for UAT,
sanitized representative data, and current ERPNext reconciliation facts. These
open inputs block only final FR-UX-031 acceptance and later implementation that
would otherwise guess ERP-specific mappings, states, numbering, ownership, or
sandbox behavior. They do not block NPI-owned domain work, explicit mocks,
contracts, tests, sandbox-ready adapters, localization, or operating
documentation, and therefore are not a global Hard Blocker.

## 9. Current release-gate decision

**Release-gate technical decision: PASS.** Repair round 1 closes
the prior formal-error, trace/retry, CSRF, unexpected ProblemDetails,
telemetry-allowlist, exact-BFF-path, transaction, and request-locale atomicity
findings, with focused regression tests plus final aggregate and runtime reruns.

Phase acceptance is `TECHNICAL_PASS_PENDING_UAT`, and Phase 4 activates
automatically under the continuous-delivery authorization. The business
UAT and provenance-backed sanitized-data obligations remain open and visible,
and no future transition authorizes production access or ERP-specific guesses.
