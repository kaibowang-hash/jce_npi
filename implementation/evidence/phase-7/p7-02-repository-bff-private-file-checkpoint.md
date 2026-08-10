# P7-02 Repository, BFF and Private-File Checkpoint

Recorded: `2026-08-10T15:58:45Z`

Status:
`PASS — PROJECT-FIRST EXECUTION, APPEND-ONLY SAMPLE AND CONTROLLED EVIDENCE BOUNDARY`

Primary requirements: `FR-TR-002`, `FR-TR-003`, `FR-TR-010`, `FR-NP-004`,
`FR-NP-005` and the `FR-TX-019` foundation.

Exact product checkpoint:
`318f1c8a624df3182280c866c371705fa3e843be`

Exact ordinary CI:
`31405749894`

## Delivered boundary

- Added one Project-first repository for exact Trial execution reads and the
  exact prepare, start, manual Actual successor, Sample Batch create/successor,
  pending private upload, clean evidence bind and audited evidence-byte
  commands authorized by the frozen contract.
- Activated only `planned -> prepared -> running`. Prepare freezes one exact
  input-lock revision before the lifecycle event; start requires that exact
  current lock and freezes the first manual Actual before the running event.
- Resolves every reference under the already locked and authorized Project.
  Inspection input must be the exact controlled-document revision whose
  independent lifecycle is currently `released`; a draft, missing,
  cross-Project, stale, hash-mismatched or superseded revision fails closed.
- Preserves multiple exact cavity references rather than collapsing them, and
  keeps actual and sample successors append-only. A Sample successor cannot
  change its stable label, cavity set, locked material, quantity or unit.
- Reuses the controlled-file mechanics: observes bounded supported bytes only
  after Project authorization, persists a private Frappe File and
  scanner-`pending` File Revision, verifies size/MIME/content hashes and
  registers rollback orphan cleanup. Upload does not imply evidence capability.
- Binds and serves evidence only after exact clean/private/live File Revision,
  Round and optional Sample revision reauthorization. Responses and snapshots
  contain no raw private URL; exact-byte access appends an audit event.
- Added actor-bound idempotency and sealed replay, exact optimistic versions,
  one command transaction, receipt-before-write/audit-before-seal ordering and
  an independent `npi_p7_02_routes_disabled` switch that defaults closed.
- Added complete direct Simplified and Traditional Chinese translations for
  the new user-visible errors and regenerated the Frappe-backed React catalog.

## Deliberately inactive

- No live Trial execution UI, fixture, controlled-Site row or visual baseline
  is added by this checkpoint. The existing P7-01 workspace remains unchanged.
- Automatic machine/acquisition import remains explicitly unavailable. No
  credential, adapter, network request, Outbox, ERPNext call, Item/Batch
  verification, reservation or production truth is introduced.
- Trial defects, quality conclusions, submission, approval, Gate mutation,
  readiness, Released Trial Summary, formal Quality Inspection/NCR, approved
  baseline and Tooling lifecycle mutation remain outside P7-02 checkpoint 2.
- Ordinary CI correctly skips controlled runtime. Disposable-Site persistence,
  rollback, scanner and route-recovery proof remains checkpoint 4.

## Changed-files to affected-tests

| Change surface | Direct evidence |
|---|---|
| lifecycle/domain | only planned/prepared/running; exact event/version/hash; immutable Actual and Sample successors |
| repository/reference containment | Project-first authorization; exact version/hash; current released document lifecycle; multi-cavity preservation; cross-object rejection |
| command transaction/idempotency | actor-bound replay; same-key conflict; receipt before writes; audit before seal; no command commit/rollback or swallowed failure |
| private upload/evidence | authorization before byte access; extension/content, size and MIME observation; pending upload; exact clean/private/live bind; no raw URL; audited bytes and orphan cleanup registration |
| API/BFF/switch | nine exact Project-first routes; closed payloads; forged server truth rejected; request ID/CSRF boundary; P7-01 and P7-02 switches independent and default closed |
| translations/catalog | generated-catalog equality and `6,139` direct English sources with `100%` `zh`/`zh-TW` coverage |
| task guard/full regression | current-task path scope, full Python/frontend/E2E/visual/secret/reconciliation checks and clean diff |

## Local verification

- Focused P7-02 API, contract, domain, repository and transaction-seam suite
  passed `69/69`, including the superseded inspection-document and unauthorized
  upload-byte negative cases.
- Full local Python discovery passed `1,527/1,527`; this includes six retained
  untracked local-development tests that were not staged. The clean CI count
  below is the authoritative tracked count.
- Frontend typecheck passed; unit tests passed `822/822` in `54/54` files;
  generated-catalog equality, formatting scope, code/boundary/style/UI audits
  and direct i18n coverage passed.
- `verify_current_task.py`, prototype approval, P0 visual governance, V1.2
  reconciliation, Python compilation and `git diff --check` passed.

## Exact-SHA CI evidence

Ordinary pull-request CI `31405749894` passed exact head SHA
`318f1c8a624df3182280c866c371705fa3e843be`:

- repository job `93511539477`: PASS with `1,521/1,521` tracked Python tests,
  task-scope verification, prototype approval, P0 visual governance, complete
  V1.2 reconciliation and repository verification;
- frontend job `93511539390`: PASS with `54/54` files and `822/822` unit tests,
  `359/359` non-visual E2E tests, statements `80.10%`, `6,139` direct English
  sources at `100%` `zh`/`zh-TW`, build/brand/install-script checks and zero
  dependency vulnerabilities;
- secret-scan job `93511539293`: PASS for the current task, current tree and
  complete pull-request branch history; and
- visual job `93511539413`: PASS at the unchanged `97/97` fixed-Linux governed
  visual matrix. No checkpoint-2 UI or baseline was introduced.

Controlled preflight and cumulative Site jobs correctly skipped because
checkpoint 2 intentionally adds no runtime fixture or Level 2 dispatch.

## Review, rollback and next checkpoint

Task Diff Review confirms that the live commands remain inside the checkpoint-1
closed contract and ownership boundary. No generic DocType CRUD, raw URL,
browser-selected scan/privacy truth, automatic import, ERP quality, conclusion,
Gate, approval, release, Tooling lifecycle or reservation authority was added.

Before retained P7-02 rows exist, this checkpoint can be reverted and a
disposable Site migrated fresh. After retained input, actual, sample, File,
evidence, lifecycle, receipt or audit history exists, rollback must disable only
the independent P7-02 routes/workspace and deliver a reviewed forward fix;
immutable history and file truth must never be deleted or rewritten.

Checkpoint 2 is PASS, not P7-02 Level 2. Checkpoint 3 alone is active: compose
the strict data source and dense trilingual Trial execution workspace with the
complete honest state matrix and affected fixed-Linux visual evidence.
Controlled runtime and Level 2 remain later checkpoint 4 work.
