# P7-05 Repository, BFF and Gate-input Checkpoint

Recorded: `2026-08-11T17:21:49Z`

Status:
`PASS — PROJECT-FIRST EXACT READINESS AND GATE-INPUT-ONLY SEPARATION`

Primary requirements: `FR-NP-001` through `FR-NP-003` and `FR-NP-006`
through `FR-NP-013`.

Exact product checkpoint:
`7bc9e641f104c025b7ccdebdfe0c3c6c6d3a020f`

## Delivered boundary

- Activated only the seven frozen template/catalog and Project readiness
  routes. Authentication precedes body parsing; mutations require CSRF and
  exact internal authority, and an independent `npi_p7_05_routes_disabled`
  switch remains default-closed unless configured to exact `false`.
- Enforced Project-first authorization for instance reads and commands.
  Template management remains internal System Manager authority; nullable-
  Project template receipts are tenant scoped rather than bound to a fake
  Project.
- Published templates and initialized Project instances freeze exact versions,
  hashes, applicability, Gate identities, categories, items, owners, due dates
  and source requirements. One active instance and one linear immutable
  successor chain are enforced without latest-value substitution.
- Resolved only exact same-tenant/same-Project Project, Work Item, released
  document/baseline, private clean File, Tooling/capacity and retained Trial
  sources. Every transitive governed source is canonicalized and revalidated;
  corrupt, ambiguous, missing or drifted identity fails closed.
- Formal ERP material/specification, quality/NCR, Run-at-rate/production, HR
  qualification and supplier-execution providers remain identity-free
  `unavailable` and make no network call. Evidence existence is never treated
  as formal approval.
- Bound idempotency to tenant, nullable exact Project, actor, operation, key and
  canonical payload. Receipt insertion, immutable successor/audit creation and
  canonical response sealing are one transaction; duplicate races replay only
  the already sealed actor-bound response.
- Validated query, command and replay responses recursively against closed
  canonical domain shapes, route identities, versions, targets and hashes.
  Extra sensitive keys, missing fields and tampered persisted responses fail
  safely instead of reaching the browser.
- Added only current applicable incomplete P0 items and one exact current
  readiness-revision dependency to the existing Gate-review input. The
  readiness repository owns unique-tip and chain validation; the Gate layer
  never guesses a latest revision.

## Deliberately inactive

- No Project readiness SPA workspace or controlled-Site runtime fixture was
  added in this checkpoint.
- P7-05 creates no Gate review cycle, event, decision, refresh, pass, close,
  reopen or transition. A later readiness successor only changes live Gate
  input and lets the existing Gate currentness policy fail closed.
- No template default, production ERP adapter/contact, automatic Work Item or
  Tooling mutation, handover, release, external projection or print effect was
  introduced.
- Rollback before retained rows is route-disable. After retained template,
  instance, receipt or audit history, rollback is route-disable plus a reviewed
  forward repair; retained immutable history is never deleted or rewritten.

## Changed-files to affected-tests

| Change surface | Direct evidence |
|---|---|
| readiness repository/source resolvers | Project-first IDOR denial, immutable template/instance succession, exact canonical source closure, no latest substitution and external zero-network truth |
| BFF/API/response validation | seven frozen routes, auth-before-body, CSRF/role/idempotency, independent switch, closed payloads and closed canonical response/replay shapes |
| receipt controller/audit transaction | nullable-Project template scope, actor-bound identity, operation/target binding, seal-once response hash and duplicate-race replay |
| Gate-review input | switch-off hash stability, P0-only blockers, exact dependency, drift, collision/capacity/corruption fail-closed and zero Gate mutation |
| OpenAPI/translations/metadata | closed request/response contracts, exact source unions, direct zh/zh-TW coverage and guarded DocType invariants |

## Local and exact-SHA CI evidence

- Focused readiness, API, contract, metadata, repository, source-closure and
  Gate regression suites passed, including `165/165` merged high-value checks.
- A clean isolated checkout of the exact patch passed `bash scripts/verify.sh`:
  `1,715` Python tests, `853/853` frontend unit tests, complete generated
  catalog/i18n/security checks and zero vulnerabilities. Fresh fixed Node
  `24.18.0` with npm `11.16.0` then passed `378/378` non-visual E2E tests.
- Pull-request CI run `31515222245` completed successfully at exact head
  `7bc9e641f104c025b7ccdebdfe0c3c6c6d3a020f`:
  - repository job `93858576011`: PASS with `1,715` tracked Python tests;
  - frontend job `93858575911`: PASS with `54` unit-test files, `853/853`
    unit tests, `378/378` E2E, `6,867` direct English sources, `100%` zh and
    zh-TW coverage, statements `80.05%` and zero vulnerabilities;
  - secret-scan job `93858575821`: PASS for the `46` committed task paths,
    current range and full pull-request history; and
  - visual job `93858575907`: PASS at the unchanged `106/106` fixed-Linux
    matrix. Artifact `9110869946` has SHA-256
    `6a78862a6a5ce64243c2e3bd7fc99b9dd54c1c53ea47b57136e9d71cbff5e580`.
- Controlled preflight job `93858576515` and runtime job `93858576840`
  skipped as expected because checkpoint 2 intentionally adds no runtime
  fixture. This checkpoint is PASS; P7-05 Level 2 is not claimed.

## Review, rollback and next checkpoint

Task Diff Review confirms product commit `7bc9e64` contains only the frozen
repository/BFF/exact-source/receipt/Gate-input boundary. It performs no Gate,
ERP or downstream mutation and preserves append-only retained history.

Checkpoint 2 is PASS. Checkpoint 3 alone is active: add the strict readiness
data source and dense trilingual Project readiness workspace with blocker-first
summary, exact category/item/owner/due/evidence/source state, score detail and
history; cover honest loading, empty, read-only, permission, validation,
conflict, processing, retry, drift and unavailable-source states,
accessibility and affected fixed-Linux visuals. The path guard adds
`frontend/src/pages/project-page.tsx` only because it is the existing
App-to-ProjectWorkspace data-source injection seam; checkpoint 3 must not
instantiate live transport inside the workspace. Controlled runtime and Level
2 remain checkpoint 4; Level 3 remains reserved for the applicable Phase, PR
or release boundary.
