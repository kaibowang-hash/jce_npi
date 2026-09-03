# P9-06 — Data Exchange, Export, Print and Retention Validation

Recorded: `2026-09-03`

Status: `IMPLEMENTATION CANDIDATE — FINAL EXACT-SHA GATES PENDING`

Requirements: `FR-RP-010`, `NFR-COM-001`

## Authorized baseline

P9-05 is complete at exact SHA
`22cc20294f37a21a64b00d6d6f2975e2988880f8`, with ordinary CI
`33712753404` and diagnostics-off Level 3 `33713119419` passing. P9-06
governance SHA `ff34547d9cb4ffd441b3203cf92d37571230bb44` passes exact-SHA
ordinary CI `33714911502` on attempt 2. Attempt 1 found only an existing P6-08
loading-state browser race; no product code changed between attempts.

## Delivered boundary

- A fixed read-only catalog describes the existing P6-07 Tooling import, P6-08
  Tooling export, P5-06 controlled print and P9-05 historical rehearsal as
  independent specialized operations. Only the already approved P9-02
  `project_portfolio.v1` and `kpi_trends.v1` permission-filtered datasets are
  exportable through P9-06.
- Published immutable profiles bind one dataset, ordered allowlisted columns,
  language, structural redaction, fixed output set, query and hard row/byte
  bounds to a canonical SHA-256. The closed deterministic ZIP contains exactly
  `manifest.json`, `report.csv`, `report.xlsx`, `report.pdf` and `README.txt`.
  Spreadsheet text is formula-neutralized before every rendering.
- The export command is System-Manager-only, tenant-bound, CSRF-protected,
  actor-idempotent and audited. It persists one private File plus immutable
  source/data/profile/package/manifest hashes, row count, actor, request and
  trace truth. Exact retry returns the durable record; download reauthorizes the
  record, private attachment and package hash and responds no-store.
- Published retention policies bind an explicit tenant, customer-reference or
  regulation-reference scope, effectivity interval and years for every closed
  category. No default production policy or precedence is inferred.
- Append-only archive records re-read one fixed source adapter and require its
  exact optimistic version/hash plus the exact policy version/hash. They retain
  source snapshot, category, retain-until, actor, request, trace and record hash
  without changing or deleting the source. There is no update, delete, purge,
  disposition or legal-hold inference endpoint.
- The Administration SPA uses only fixed LaunchFlow BFF routes. It exposes
  capability, profile, package, policy and archive truth with loading, empty,
  disabled, processing and fault states in English, Simplified Chinese and
  Traditional Chinese. The route is independently default-disabled.

## Local verification

- Focused Python suite: `23/23` PASS across domain, deterministic package,
  API/BFF, OpenAPI, DocType metadata, security and runtime-verifier contracts.
- Full repository Level 2: `2970/2970` PASS, including reconciliation,
  prototype governance, security scans, Python compilation and diff hygiene.
- Focused React/router suite: `43/43` PASS before the final command-coverage
  addition; the complete frontend suite then passed `1140/1140`.
- Frontend coverage: statements `80.06%`, branches `79.49%`, functions
  `82.09%`, lines `82.64%`.
- P9-06 live browser suite: `3/3` PASS across `en`, `zh` and `zh-TW`, including
  accessibility, mixed-language and overflow assertions.
- Generated catalogs, TypeScript, ESLint, Prettier, Stylelint, boundaries,
  industrial UI and i18n all PASS. The catalog audit covers `9322` literal
  English sources with `100%` direct `zh` and `zh-TW` coverage.
- Production build, lazy-route/locale budgets and dependency audits PASS. The
  in-place display-brand audit is intentionally not reported as an aggregate
  local PASS because user-owned untracked public images outside P9-06 remain
  present and unmodified. The clean exact-SHA ordinary CI is authoritative.
- Shell syntax, Python compilation and runtime-verifier contract tests PASS.
  A direct macOS disposable-Site run is not inferred because the retained Bench
  virtual environment points to its Linux container interpreter. The governed
  Linux Level 3 lane performs the real migrations and cumulative synthetic
  runtime, including P9-06 profile/export/download/policy/archive replay and
  stale-source rejection with `productionContact=false`.

## Fault and recovery evidence

Static, unit, browser and runtime contracts cover empty reports, permission
denial, structural redaction, formula cells, hard bounds, invalid PDF output,
stale profile/policy/source hash, mismatched replay identity, private File drift,
timeout-after-commit durable replay, failed command truth and default-disabled
routes. Any package-render failure occurs before the export record and audit are
created inside the transaction. Rollback disables routes and reverts only P9-06
code/schema while retaining already accepted immutable history for reviewed
forward correction.

## Final evidence slots

The candidate exact SHA is the Git commit containing this document. Completion
requires one exact-SHA ordinary CI PASS and one diagnostics-off Level 3 PASS at
that same SHA. Until both pass, P9-06 remains incomplete and P9-07 product work
is not authorized. No production LaunchFlow or ERPNext contact occurred.

## First exact-SHA ordinary result and batched test adaptation

Candidate SHA `4341dd6b700ac415a7198356231158f69d813ad7` reached ordinary
CI `33718667941`. Repository, secret, visual and E2E shard 1 passed. The run
failed only because the new governed Data Exchange command was not reflected
in two test contracts: the P9-06 workspace test used lint-prohibited non-null
fixture assertions and an empty mock body, while the existing Shell navigation
test still expected ten commands and selected the former sixth command by its
old index. E2E shard 2 otherwise passed `233/234` tests.

One behavior-neutral batch now validates required fixtures explicitly, gives
the anchor mock an explicit return, and updates the complete Shell command
contract to eleven entries while retaining the same current-Project navigation
assertion. ESLint passes; the complete frontend unit/coverage suite passes
`1140/1140`; and the affected Shell plus P9-06 browser suite passes `13/13`.
The replacement exact-SHA ordinary CI and diagnostics-off Level 3 remain the
only outstanding gates. No product behavior, CI workflow, production system or
user-owned file changed.
