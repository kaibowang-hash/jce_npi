# P6-07 Bounded Worker, Partial Result, Correction, Retry and Rollback Checkpoint

Recorded: `2026-08-09T11:26:35Z`

Status:
`PASS — BOUNDED AFTER-COMMIT EXECUTION, IMMUTABLE PARTIAL TRUTH, FAILED-ROW RETRY AND STRICT ROLLBACK`

Requirements:
`FR-TX-012`, `FR-TX-013`, `FR-TX-014`, `FR-TX-015`, `FR-TX-016`,
`FR-TX-017`, `FR-TX-018` and `UX-016` technical foundation

Exact stable checkpoint:
`abd32261d9588def3063e8e4a2094fb743ff5fb2`

Primary product commit:
`7233c88f9ee58a2fd10ca81244532d2c2ba4064c`

## Delivered boundary

- Added an execution command that persists one durable job and schedules work
  only through an after-commit callback. The worker processes at most `25`
  rows per bounded run and derives terminal state from durable immutable row
  truth rather than an optimistic request response.
- The worker reauthorizes the preserved actor, Project/customer, exact clean
  private File Revision and hash, immutable preview and hash, active mapping
  activation and optional correction artifact before processing a run.
- Added six guarded additive DocTypes for exact mapping activation, job, row
  result, target binding, correction artifact and reconciliation revision.
  Metadata installs no mapping activation, job, target row or business rule.
- Added nine exact execution/result routes: execute, bounded job collection,
  exact job detail, failed-row retry, correction creation, audited correction
  content download, reconciliation, rollback evaluation and rollback.
- Each row and field result is immutable and retains worksheet/row/source
  provenance, transformation and mapping versions, stable result/error code,
  complete English source message, exact target identity/version/hash when
  applicable and request/trace identity. Earlier attempts are never rewritten.
- Successful rows are never retried. A retry creates a successor job bound to
  the latest failed retryable rows and the exact correction artifact ID/hash;
  attempt greater than one cannot execute without that artifact authority.
- Correction output is private, formula-safe, hash-bound, allowlisted and
  audited. Content download is binary-safe and rechecks Project authorization.
- Reconciliation records missing, changed and exact target truth as an
  immutable successor. It reports discrepancies and performs no silent repair.
- Rollback re-evaluates the exact batch-created target set under locks. It may
  delete only canonical Part/Part Revision UUID targets that are unchanged at
  the imported version/hash and have zero downstream references. Updated,
  changed or downstream-used objects produce a durable `rollback_denied`
  result; the all-or-nothing operation leaves no partial deletion.
- Every command retains actor-bound sealed idempotency, one transaction,
  append-only audit and exact replay/conflict behavior. Generic create/update/
  delete remains controller-denied; the exact rollback path additionally
  requires the closed Tooling command-write flag.

## Deliberately unavailable

- `DR-REC-007` remains open. Production mapping activation is unavailable.
  The only active authority is an exact visibly synthetic fixture mapping,
  installed outside migrations and bound to the known generated fixture,
  synthetic customer, Project, source signature and effective window.
- No customer workbook is committed or read. The deterministic synthetic
  fixture remains the only executable workbook evidence.
- No live import SPA or generic Phase 8 job center is delivered at this
  checkpoint.
- No ERPNext endpoint, credential, network call, Outbox row, Asset mapping or
  ERP-owned location, inventory, maintenance, procurement, manufacturing,
  quality, cost or finance truth is reachable.
- `DR-REC-008` continues to deny rollback of updated pre-existing, changed or
  downstream-used targets. There is no caller-selected destructive target.
- Controlled disposable-Site runtime proof remains checkpoint 5 work.

## Local affected and regression evidence

- focused execution domain/repository/API/metadata and exact rollback suites:
  PASS;
- complete tracked Python discovery: `1,341/1,341` PASS;
- after-commit enqueue, bounded resume, worker reauthorization, partial and
  retryable/final truth, successful-row non-duplication, correction hash/
  authorization, immutable reconciliation and all-or-nothing rollback tests:
  PASS;
- production-mapping-unavailable, no-ERP/no-network/no-Outbox, raw-log
  redaction, generic-mutation denial, permission, CSRF, IDOR, replay,
  conflict and transaction rollback tests: PASS;
- frontend catalog generation/check, typecheck, lint, style/boundary,
  industrial UI, production build and `777/777` unit tests: PASS;
- i18n audit: `5,379` literal English sources with 100% direct `zh`/`zh-TW`
  coverage and no mixed-language violation;
- frontend coverage: statements `80.20%`, branches `79.05%`, functions
  `82.10%`, lines `82.35%`; and
- non-visual Playwright: `337/337` PASS.

The host Node `24.2.0`/npm `11.3.0` does not match the repository-pinned Node
`24.18.0`/npm `11.16.0`; the pinned GitHub runtime below is the authoritative
full Gate. Isolated clean-tree verification excluded the user's existing
untracked brand asset. All user-owned files, Darwin snapshots, local evidence
and `implementation/LAST_RUN.md` were preserved and excluded.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| execution domain and worker | bounded 25-row run, durable state derivation, reauthorization, partial/retryable/final and successful-row non-duplication tests |
| execution repository and BFF | exact nine-route registration, Project-first authorization, after-commit scheduling, CSRF, actor-bound idempotency, transaction/audit order, replay/conflict/rollback tests |
| activation/job/result/binding metadata | guarded generic CRUD, immutable history, exact fixture-scope activation, uniqueness and forbidden migration-default tests |
| correction and reconciliation | private formula-safe allowlist/hash, binary audited download, failed-row-only successor and immutable discrepancy tests |
| Part/Revision exact rollback guard | canonical UUID, exact batch binding/version/hash, downstream reference, closed write flag and all-or-nothing denial tests |
| OpenAPI, ownership and translations | route/role/transaction/audit contract assertions plus generated catalog and complete direct trilingual audit |
| governed footer fingerprints | eighteen artifact-reviewed Linux actuals promoted byte-for-byte; complete `88/88` fixed-Linux CI |

## Exact-SHA CI and bounded visual repair

Primary product commit `7233c88f9ee58a2fd10ca81244532d2c2ba4064c`
ran ordinary CI
[`31309906513`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31309906513).
Repository job `93235984139` passed the complete repository Gate. Visual job
`93235984148` passed `70/88` and failed exactly the eighteen durable P0
screenshots after the additional translated sources changed only the bottom
catalog fingerprint. Controlled runtime job `93235984534` correctly skipped.

Artifact `9037091907`, digest
`sha256:6b445895d32f37b26b134fa65463b9c2944de8d421e2d48cd1923e575c3a1265`,
retains all eighteen actual/diff pairs. Exact RGB comparison against the
tracked Linux baselines found `755` differing pixels in every English image
and `751` in every `zh`/`zh-TW` image. All images had zero changed pixels above
`y=860`; half-open boxes were confined to English
`x=559..677, y=882..892` and Chinese `x=496..613, y=882..892`. No business
region, component, layout, user copy, state, assertion, matrix, tolerance,
threshold or PASS criterion changed.

Isolated repair `abd32261d9588def3063e8e4a2094fb743ff5fb2` copied only the
eighteen reviewed CI actuals byte-for-byte to their exact tracked Linux
targets. It staged no user-owned or Darwin file.

Final ordinary CI
[`31310360136`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31310360136)
passed exact stable checkpoint `abd32261`:

- repository job `93237139821`: PASS — `1,341/1,341` tracked Python tests,
  `777/777` frontend unit tests, `337/337` non-visual E2E, `5,379` literal
  English sources with 100% direct `zh`/`zh-TW`, statements `80.20%`, branches
  `79.05%`, functions `82.10%`, lines `82.35%`, zero dependency
  vulnerabilities and both current/history secret lanes (`29` pull-request
  commits and `304` complete branch commits scanned with no leaks);
- visual job `93237139805`: PASS — `88/88` fixed-Linux cases;
- controlled runtime job `93237140181`: correctly skipped;
- visual artifact `9037230235`, digest
  `sha256:d00d71b8df1b592879e800cf82d12e1879622efdef61d9b4495e0662009052a6`;
  and
- Gitleaks artifact `9037284616`, digest
  `sha256:7b747ed2a35fe510d19951b7b6c94c3fb7ea28ce8c60886a258900c8bf8d7c52`.

## Review, rollback and next checkpoint

Task Diff Review confirms the checkpoint is additive, Project-first and
bounded. Execution is exact-fixture-only, durable partial truth cannot be
reported as success, successful mutation cannot be replayed by a retry, and
no external system is contacted. Rollback is a reviewed forward operation:
disable the P6-07 route/worker switches while retaining all source, mapping,
preview, job, result, correction, reconciliation, audit and receipt history.

Checkpoint 3 is PASS. P6-07 remains in progress. Autopilot next implements
only checkpoint 4: the dense eight-step selected-Project live import
workspace, stable step rail/table-tree/inspector/progress layout, complete
mapping-unavailable/confirmation/loading/empty/permission/read-only/conflict/
queued/processing/partial/success/retryable/final/rollback states, authorized
correction/retry/rollback-denial surfaces and direct English/`zh`/`zh-TW`,
keyboard, focus, component, browser and fixed-Linux visual evidence.
Controlled Site, production mapping, customer workbook and ERPNext contact
remain inactive.
