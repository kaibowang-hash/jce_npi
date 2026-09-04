# P9-06 — Data Exchange, Export, Print and Retention Plan

Recorded: `2026-09-03`

Status: `IMPLEMENTATION CANDIDATE — FINAL EXACT-SHA ORDINARY AND LEVEL 3 REQUIRED`

Requirements: `FR-RP-010`, `NFR-COM-001`

## Accepted predecessor

P9-05 is complete at exact SHA
`22cc20294f37a21a64b00d6d6f2975e2988880f8`. Ordinary CI `33712753404`
and diagnostics-off Level 3 `33713119419` pass, including fresh cumulative
disposable-Site runtime `100517575541` with `productionContact=false`.

## Audit result

The approved architecture and current specialized implementations remain the
default-correct baseline:

- P6-07 owns one closed Tooling workbook import with immutable source,
  structural detection, versioned mapping, preview, partial truth, correction,
  reconciliation and guarded rollback. It is not a generic import service.
- P6-08 owns Project-first Tooling List export. Its fixed views, selected or
  filtered scope, private immutable package, redaction, formula neutralization,
  actor-bound replay and audit remain unchanged.
- P5-06 owns template-registered controlled print with immutable source
  snapshot, frozen private PDF, exact hashes, permissions, audit and
  idempotency. Production templates, signers, browser/device print and numbered
  copies remain held.
- P9-02 owns permission-filtered `project_portfolio.v1` and `kpi_trends.v1`
  reporting truth with explicit source and availability. It intentionally has
  no export command.
- P9-05 owns a separate default-disabled non-production historical rehearsal.
  Its bundle and correction artifacts are catalogued but never dispatched by a
  generic Data Exchange command.
- My Work export remains fail closed under `export_contract_required`; P9-06
  does not silently convert the general grid into an export surface.
- There is no current configurable retention-policy or read-only archive
  engine. Existing private immutable File Revision custody is reusable but
  does not itself satisfy configurable retention years.

No new production ERPNext fact is required. This transition and its product
batch must not contact production ERPNext or LaunchFlow.

## Frozen minimal product slice

### Fixed Data Exchange catalog and report export

The catalog is read-only and code-owned. It lists the existing specialized
capabilities and only two exportable report datasets:
`project_portfolio.v1` and `kpi_trends.v1`. It accepts no caller-selected
DocType, SQL, report name, method, query, source adapter, field or template.

A versioned published export profile binds exactly one dataset version, an
ordered allowlist of known column IDs, output language, a structural redaction
profile, output members and hard row/byte bounds. No production profile is
seeded. Publishing freezes an exact canonical hash; a changed definition needs
a successor version.

An export command requires System Manager, CSRF, exact profile version/hash,
actor-bound idempotency and the independent P9-06 route switch. It reuses the
P9-02 permission-filtered repositories and persists a private immutable
artifact plus source/profile/data/package hashes, request, actor, trace,
timestamps, row counts, status and audit truth. Replay returns the durable
result and timeout-after-commit is reconciled instead of blindly redispatched.

The closed `data-exchange-report-package.v1` ZIP contains a canonical manifest,
safe CSV, deterministic XLSX, controlled PDF and README. Member names, row and
byte counts are bounded; all spreadsheet cells are formula-neutralized;
redacted columns never enter generated members. Output order, timestamps and
ZIP metadata are deterministic. Download is permission checked, snapshot-bound,
private, no-store and attachment-only. PDF covers controlled report output, not
browser/device print, production forms or numbered copies.

### Published retention policy and append-only archive truth

One immutable published policy version contains:

- closed scope kind: tenant default, exact customer reference or exact
  regulation reference;
- exact scope reference where required;
- inclusive effective-from and optional exclusive effective-until;
- explicit retention years for project, quality, change, file, Data Exchange
  export and controlled-print categories;
- publisher, published time, schema version and canonical hash.

The task seeds no default production policy and invents no precedence between
matching policies. Selection is explicit: the archive request supplies one
published policy version and the server validates category, effectivity and
scope. Ambiguous, absent, draft, stale, mismatched or future policy versions
fail closed.

An append-only archive record binds one allowlisted source kind to exact source
ID, optimistic version, source hash, immutable source snapshot or private File
reference, selected policy version/hash, category, calculated retain-until,
actor, trace and audit identity. Closed source adapters cover Project, immutable
engineering-change revision, immutable quality/trial evidence, File Revision,
Data Exchange export and controlled print. Archive creation does not alter the
source. Archive records have no update/delete/purge/dispose command; physical
disposition and legal-hold precedence remain future policy work.

## Security and truth rules

- Browser traffic terminates only at LaunchFlow BFF routes.
- Server-side role, tenant, Project, object and file permissions remain
  authoritative. UI state is never authorization.
- Private artifacts expose no filesystem path, File URL or raw source value.
- Redaction is structural: excluded fields are absent from manifest, CSV, XLSX,
  PDF, preview, audit detail and error output.
- Failures use stable problem codes plus request/trace IDs. HTTP success never
  represents export, archive or external execution success unless durable state
  proves it.
- Existing P6-07, P6-08, P5-06 and P9-05 command endpoints remain separate.
- Frappe/ERPNext core, ERP-owned masters, integrations and production systems
  do not change.

## Changed-files to affected-tests map

| Change | Required evidence |
| --- | --- |
| Domain, package and repository | canonical/hash, profile/policy validation, permission, redaction, CSV/XLSX/PDF, formula, bounds, idempotency, stale/conflict and archive immutability tests |
| DocTypes and API/OpenAPI | metadata, no-delete/no-generic-dispatch security, normal/fault/timeout-after-commit/partial/unavailable routes and disposable-Site verifier |
| SPA and BFF source | unit, router, E2E, accessibility, overflow and English/`zh`/`zh-TW` truth |
| Translation catalogs | extraction, direct coverage and mixed-language scans |
| Runtime shell | syntax, verifier contract, preflight and cumulative disposable-Site Level 3 |
| Governance/trace | current-task verifier, reconciliation verifier, repository Gate and diff hygiene |

## Acceptance and test matrix

The product batch must prove normal, empty, denied, redacted, bounded,
formula-bearing, stale-profile, version/hash conflict, unavailable source,
timeout-after-commit, idempotent replay, partial generation failure, private
download and audit cases. Retention tests cover draft/future/expired/mismatched/
ambiguous/no-policy failures, category duration calculation, source drift,
append-only archive truth and absence of delete/disposition. UI evidence covers
all three languages, keyboard/accessibility, industrial density and no mixed
language. Level 2 precedes one final exact-SHA ordinary CI and the sole
diagnostics-off Level 3 with cumulative disposable-Site verification.

## Rollout, monitoring and rollback

Migrate DocTypes first, then deploy backend and SPA with the P9-06 route switch
disabled. Create only reviewed non-production profiles and policies for
controlled UAT. Monitor stable problem codes, audit entries, artifact counts,
generation duration/size, failed/replayed requests, missing coverage and stale
source/profile/policy conflicts. Production profile/policy creation and route
activation are outside this task.

Rollback disables the routes and reverts only the independent P9-06 code and
schema paths. Every published policy, export artifact, archive record, receipt
and audit row is retained as invalidated history; repair is a successor profile,
policy or forward correction, never destructive deletion.

## Implemented candidate

The governance transition at exact SHA
`ff34547d9cb4ffd441b3203cf92d37571230bb44` passed ordinary CI
`33714911502` on attempt 2. The first attempt exposed only an existing P6-08
loading-state E2E race; the exact-SHA rerun passed without a product change.
That PASS authorized the single P9-06 product batch now recorded in
`p9-06-validation.md`.

The candidate implements the frozen slice without changing the audited
specialized flows. Its independent routes remain disabled unless the Site
configuration contains the exact value `npi_p9_06_routes_disabled=false`. No
profile or retention policy is seeded, no automatic disposition exists, and no
production LaunchFlow or ERPNext connection was made. Final completion remains
strictly external: one exact-SHA ordinary CI PASS followed by one diagnostics-off
Level 3 PASS at the same candidate SHA.
