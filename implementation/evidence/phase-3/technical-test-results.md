# Phase 3 Technical Test Results

Execution date: 2026-07-22

Outcome: **PASS for the completed Phase 3 technical checks below**

This record is a durable summary of the repaired Phase 3 candidate. It supports
the separate release-gate decision but is not business UAT, a
production-readiness decision, or evidence that prototype fixtures are
representative operational data.

## Command results

| Command / gate | Result | Evidence summary |
|---|---|---|
| `npm ci` | PASS | 432 packages installed; 433 packages audited from the committed lockfile |
| `make verify` | PASS | 58/58 Python repository/API/security/localization tests and the complete frontend verification passed |
| `npm run verify` | PASS | Generated artifacts, TypeScript, lint/format/style/boundary/UI/i18n checks, 110/110 frontend unit/component tests with coverage, production build, and both npm audits passed |
| `npm run test:e2e` | PASS | The post-fix run passed 63/63 non-visual Chromium tests in 2.6 minutes |
| `npm run test:visual:update` | PASS | All 129 deterministic screenshots were force-regenerated with `--update-snapshots=all` and passed in 4.3 minutes |
| `npm run test:visual` | PASS | 129/129 screenshots matched the regenerated baseline at `maxDiffPixelRatio: 0` in 3.9 minutes without update mode |
| Six-image manual visual review | PASS | Representative English, Simplified Chinese, Traditional Chinese, 150%-equivalent, error-state, and field-tablet images passed at original resolution |
| `make frappe-site-init` | PASS | The local Frappe Site/app installation and migration passed against Frappe 15.115.4 at commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` |
| `make frappe-runtime-verify` | PASS | Normal Website User, 556-entry catalogs, CSRF and malformed-request contracts, fresh-session locale persistence, Administrator isolation, trace correlation, no-store delivery, and exact fixture deletion passed |

## Coverage

The repaired `vitest --coverage` report covers the Phase 3 frontend source set:

| Metric | Covered / total | Result |
|---|---:|---:|
| Statements | 4,319 / 4,646 | 92.96% |
| Branches | 784 / 863 | 90.84% |
| Functions | 144 / 160 | 90.00% |
| Lines | 4,319 / 4,646 | 92.96% |

The portable machine-readable aggregate is in
`implementation/evidence/phase-3/coverage/coverage-summary.json`. It contains
no workspace-specific absolute paths.

## Production build and dependency security

- Vite transformed 390 modules.
- Main JavaScript: 761.17 kB minified / 190.88 kB gzip.
- CSS: 225.79 kB minified / 22.86 kB gzip.
- `npm audit`: zero known vulnerabilities.
- `npm audit --omit=dev`: zero known production-dependency vulnerabilities.

The JavaScript bundle remains above Vite's 500 kB warning threshold. The
warning is retained as visible performance debt rather than suppressed. Full
dependency and rollback detail is recorded in `dependency-review.md`.

## API, browser, accessibility, and localization scope

The completed unit and local-runtime checks cover strict NPI BFF path handling,
same-origin credentials, caller-supplied CSRF stripping, fail-closed unsafe
requests without a trusted session token, safe Problem Details handling,
request/trace correlation, language-update reconciliation, and a finite
privacy-safe telemetry allowlist. The loopback runtime separately proves
missing and wrong CSRF responses, malformed JSON, missing/extra/wrong-type
fields, unchanged state after rejected requests, no-store bootstrap delivery,
and matching response-body/header trace identifiers.

The final Python test added the cache-failure rollback boundary: if per-user
cache invalidation fails after `User.save()`, the API returns a retryable safe
500, the database transaction rolls back, the in-memory User language is
restored, and the current request locale remains unchanged. The response cannot
claim or render a language that was not committed.

The final 63-test non-visual suite exercised the six prototype workflows;
every required deterministic page state; keyboard selection and dialog focus;
dirty-navigation protection; route/locale persistence; one-primary-action
rules; real iX accessible names and disclosure attributes; WCAG A/AA axe
checks; computed Classic Light token constraints; desktop and zoom-equivalent
layouts; a 768x1024 field-tablet path; and a 390x844 field-phone interaction
path.

Language checks traversed visible DOM text, relevant attributes, and open
shadow roots. English, `zh`, and `zh-TW` passed the non-allowlisted
mixed-language scan. The static i18n gate passed literal-source,
source/context, placeholder, catalog-coverage, retain-term, controlled-term,
and Chinese Latin-token checks. The direct `zh` and `zh-TW` catalogs each
contain 556 entries, and the generated browser catalog version is
`12e5adf665b2cd30`. The local Frappe runtime delivered 556 messages per locale
with a full SHA-256 catalog version and proved the authenticated Website User
preference across fresh sessions.

The 129-case visual refresh and clean exact comparison both passed. Six
representative regenerated images also passed manual review at original
resolution. The normal-user runtime proof is recorded in
`runtime-validation.md`.

## Known technical and acceptance boundaries

- The Worklist uses a bounded prototype fixture transport behind the data
  source abstraction; this run does not prove live BFF paging or production
  scale/performance.
- Browser time is fixed to UTC for deterministic prototype evidence; user and
  company timezone resolution is not yet connected to a live session.
- Notification, mail, print, and export localization is covered by shared
  renderer/formatter infrastructure tests, not live delivery or document
  generation pipelines.
- Telemetry is a validated, privacy-safe in-memory prototype recorder; there is
  no live ingestion endpoint or durable operating metric.
- ERPNext execution content is an honest contract-backed prototype. No
  production ERPNext system, formal write, or real ERP deep link was used.
- Notification counts and refresh/deep-link capabilities remain explicitly
  unavailable or prototype-only rather than claiming a successful live action.
- The six technical workflows use labelled fixtures. Provenance-backed
  sanitized operational data has not been supplied.
- Project Management, Engineering/Tooling, and Quality business UAT remains
  unsigned. See `business-uat.md`; no technical test substitutes for that
  review.
