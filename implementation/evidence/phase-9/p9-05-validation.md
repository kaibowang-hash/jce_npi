# P9-05 — Historical Migration Rehearsal Validation

Recorded: `2026-09-03`

Status: `IMPLEMENTATION CANDIDATE — FINAL EXACT-SHA ORDINARY CI AND LEVEL 3 PENDING`

## Authorized baseline

P9-04 final SHA `fa82f3e3dcc7a9474ea51a1356130d5cbc02adee`
passes ordinary CI `33702330209` and Level 3 `33702723201`. P9-05 governance
SHA `4d54fbef67cb9111618ded2ae2abd0cc47942167` passes exact-SHA ordinary CI
`33704386277`. The implementation keeps the approved LaunchFlow architecture,
data ownership and P6-07 contract intact. It contacts neither production
LaunchFlow nor production ERPNext.

## Delivered boundary

- A closed `historical-migration-rehearsal.v1` ZIP accepts exactly one manifest
  and four CSV members for Projects, Tooling mappings, existing File Revision
  indexes and approved reference links. Standard-library inspection bounds
  archive bytes, expanded bytes, compression ratio, member names, row/field/
  cell counts, UTF-8 shape, formulas, hashes, types, versions and references.
- The source is one exact clean private `NPI File Revision`. Batch and preview
  identities bind its UUID, optimistic version, SHA-256, manifest hash, actor,
  request and trace. Preview is immutable and reports deterministic
  create/link/skip/blocked decisions, field names, finding codes and hashes.
- Four append-only support DocTypes hold batch, preview, job and exact target
  binding truth. Operation-specific BFF routes require System Manager, CSRF,
  idempotency and exact versions/hashes. Execution is disabled unless both the
  route and non-production rehearsal switches have exact enabled values.
- The worker reauthorizes actor, source File Revision and bytes, preview and
  manifest before processing. Results distinguish queued, processing, partial,
  retryable/final failure and success; replay returns the durable job rather
  than redispatching uncertain work.
- Correction CSV is private and contains only failed source identities and
  finding codes. Download is snapshot-bound and sent as an attachment with
  no-store/nosniff policy. Reconciliation observes only allowlisted target
  hashes. Rollback retains every target and changes only safe exact bindings;
  Project creation or drift records forward-correction truth.
- The Administration SPA uses only the LaunchFlow BFF. It exposes dense source,
  preview, finding, job, correction, reconciliation and rollback truth,
  automatic active-job refresh and a single confirmation surface. Raw
  difference values are not rendered. English, Simplified Chinese and
  Traditional Chinese use the existing Frappe catalog chain.

## Verification completed before the candidate commit

- Python focused suite: `26/26` PASS across bundle, domain, OpenAPI, metadata,
  API, security and runtime-verifier contracts.
- React focused suite: `39/39` PASS across data source, workspace and router.
- TypeScript project typecheck: PASS.
- Browser functional/accessibility suite: `3/3` PASS across English, Simplified
  Chinese and Traditional Chinese, including mixed-language and overflow scans.
- i18n extraction and catalog audit: `9184` literal English sources with `100%`
  direct `zh` and `zh-TW` coverage; generated catalogs are current.
- Shell syntax, Python compilation and `git diff --check`: PASS.
- Repository Level 2: `2947/2947` tests PASS with reconciliation and repository
  verification PASS.
- Frontend Level 2 components: `1127/1127` tests PASS; statements `80%`,
  branches `79.45%`, functions `82.03%`, lines `82.59%`; lint, format, style,
  boundary, industrial UI, i18n, production build and build budgets PASS. Both
  dependency audits report zero vulnerabilities. The tracked-tree display-brand
  audit passes in an isolated snapshot.
- The local `npm run verify` wrapper is not recorded as an aggregate PASS: the
  host has npm `11.3.0` rather than the repository-required `11.16.0`, so its
  `approve-scripts` subcommand is unavailable, and user-owned untracked public
  images intentionally retained outside this task contaminate the in-place
  brand scan. Neither is staged. The clean exact-SHA ordinary CI is the
  authoritative aggregate frontend result.
- A direct macOS disposable-Site run is not accepted because the retained Bench
  virtual environment is a Linux build with a broken host interpreter symlink.
  No runtime result was inferred. The governed Linux Level 3 lane performs two
  migrations and runs the synthetic P9-05 partial/replay/stale/correction/
  reconciliation/logical-rollback verifier with `productionContact=false`.

## Final evidence slots

- Candidate commit: `PENDING_EXACT_SHA`
- Exact-SHA ordinary CI: `PENDING`
- Diagnostics-off Level 3: `PENDING`
- Controlled runtime job/artifact/checksum: `PENDING`
- Release-gate result: `PENDING`

These slots intentionally remain pending inside the candidate commit. The CI
and Level 3 runs are bound externally to that immutable exact SHA; no follow-up
documentation commit may be used to reinterpret a failing candidate.

## Rollback

Keep both P9-05 Site switches disabled. Revert only the independent P9-05
bundle/domain/repository/DocType/API/UI/verifier paths. Retain any accepted audit
or rehearsal evidence as invalidated history. Never delete a target to simulate
rollback; use reviewed forward correction whenever a target changed or was
created by the rehearsal.
