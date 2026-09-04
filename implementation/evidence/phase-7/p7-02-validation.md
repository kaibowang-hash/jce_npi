# P7-02 Level 2 Validation — Locked Inputs, Actuals, Samples and Evidence

Recorded: `2026-08-11T05:35:00Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`3a267196d11921ba1111a0774f5f85bd8647ed9f`

Primary requirements:
`FR-TR-002`, `FR-TR-003`, `FR-TR-010`, `FR-NP-004`, `FR-NP-005` and
`FR-TX-019` foundation.

Truthful disposition:
`TECHNICAL_VERIFIED_MANUAL_FOUNDATION_MACHINE_IMPORT_HELD`

## 1. Outcome

P7-02 delivers the frozen minimum complete vertical slice for Trial execution:

- immutable exact-version input-lock revisions over product/design, Part,
  Tooling Revision, physical Set/cavity/process, material, parameter,
  inspection-document and controlled-evidence inputs;
- exact `planned -> prepared -> running` transitions with one retained lock and
  first execution context, without activating analysis, conclusion or approval;
- append-only Trial Actual revisions with explicit measured/not-measured state,
  unit, source, acquisition mode and timestamps, never copied from Customer
  Standard or represented as an Approved Process Baseline;
- stable Sample Batch identity and immutable successor revisions preserving
  material, cavity, quantity, packaging, destination and feedback lineage;
- bounded private upload into scanner-pending state, exact clean/private/live
  File Revision binding and Project-first audited byte access with no raw URL;
- actor-bound idempotency, optimistic conflict, one-transaction append-only
  history/audit, independent route control and fail-closed generic mutations;
  and
- a dense industrial English, Simplified-Chinese and Traditional-Chinese Trial
  execution workspace with truthful complete state coverage.

Automatic machine/acquisition-system import, production ERPNext access,
formal Item/Batch verification, Quality Inspection/NCR, conclusion, approval,
Gate or Tooling lifecycle mutation, reservation, external projection and
production print remain explicitly unavailable or assigned to later tasks.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
| --- | --- | --- |
| `FR-TR-002` | `TECHNICAL_VERIFIED_MANUAL_FOUNDATION_MACHINE_IMPORT_HELD` | Exact machine/material/environment context and parameter Actual successors are live; only manual acquisition is authorized. |
| `FR-TR-003` | `TECHNICAL_VERIFIED` | Pending private upload and exact clean File Revision evidence bind/access are live and runtime proven for Round/Sample evidence. |
| `FR-TR-010` | `TECHNICAL_VERIFIED_MANUAL_FOUNDATION_MACHINE_IMPORT_HELD` | Manual source/time/confirmation is proven; no adapter, credential, network path or inferred machine result exists. |
| `FR-NP-004` | `TECHNICAL_VERIFIED_MANUAL_FOUNDATION_MACHINE_IMPORT_HELD` | Exact parameter definitions/windows and append-only Trial Actual revisions are proven without automatic acquisition or baseline approval. |
| `FR-NP-005` | `TECHNICAL_VERIFIED` | Stable Sample Batch identity and append-only cavity/material/quantity/packaging/destination/feedback lineage are proven. |
| `FR-TX-019` | `TECHNICAL_VERIFIED_FOUNDATION` | Customer Standard, Trial Actual and Approved Baseline remain disjoint; P7-02 is the single Trial Actual owner and baseline approval remains later authority. |

The aggregate disposition is intentionally narrower than complete production
acceptance and cannot be read as machine integration or formal quality truth.

## 3. Exact-SHA ordinary and controlled Gates

Ordinary pull-request CI `31432120639` passed exact SHA `3a26719`:

- repository `93597777986`: `1,524/1,524` tracked Python tests and complete
  repository verification PASS;
- frontend `93597778042`: `54/54` files, `832/832` unit tests,
  `365/365` E2E, `6,311` direct trilingual sources, zero vulnerabilities and
  clean generation/type/lint/build checks;
- visual `93597778040`: `100/100` fixed-Linux governed cases PASS;
- secret scan `93597778102`: current-task guard plus current-tree and complete
  branch-history Gitleaks PASS with no leaks;
- visual artifact `9079635751`, upload digest
  `sha256:cf59d738c637b4cd4bb1b59a8bd2c68b19005122676deba47746237eb13b588f`;
  and
- Gitleaks artifact `9079533262`, upload digest
  `sha256:99f44a783def10ef760dc5033a8bd8b9f56b54038b7d1a2f5bbe28315e0dc1a5`.

Optimized exact-SHA controlled Gate `31432837104` then passed the same SHA:

- controlled preflight `93600090390` verified the exact successful prior
  pull-request run, repository, event, SHA and required four jobs;
- cumulative runtime `93600205449` passed scope `p5-01-through-p7-02` on
  pinned Frappe commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`;
- runtime artifact `9079952599`, `p7-trial-runtime-31432837104`, contains
  `result=PASS` and local content digest
  `sha256:30bbc289cc9b288a62ad40a10f1143386696d06e879d4cf73f2de98b17cbf284`;
  and
- prior-Gate attestation artifact `9079803062` contains the exact successful
  run `31432120639` and local content digest
  `sha256:4ef8513f9a2aeed84f2bb4b27edd70a94aaddde8ca842e2f53e3141beec26bad`.

The controlled dispatch intentionally skipped repeated repository/frontend/
visual/secret jobs only after its fail-closed exact-SHA preflight accepted the
complete prior PR Gate. This is the P7-02 Level 2 Task Gate; the Phase 7 final
Level 3 Gate remains mandatory at the Phase boundary.

## 4. Controlled truth and negative matrix

The disposable Site proves prepare/start, Actual successor, Sample successor,
pending upload, clean evidence bind and exact-byte access across a fresh
process. It also proves:

- exact input/reference versions and hashes never move to latest;
- same-process replay, same-key/different-payload conflict and cross-process
  replay without row, receipt, audit or response drift;
- semantic reference-set replay independent of input order;
- guest/external/unrelated/cross-Project/object substitution denial and
  authorization before secondary object or File resolution;
- pending/infected/public/mismatched/file-content denials, exact stored-byte
  SHA/size/MIME/Frappe content-hash checks and Frappe-owned safe storage name;
- generic update/delete denial, transaction rollback and immutable history;
- independent P7-02 route disable/recovery while predecessor Trial routes stay
  available;
- additive migrations, raw-log sentinel/redaction checks, zero ERP/network/
  Outbox traffic and disposable cleanup; and
- truthful `machine_import=unavailable` with no adapter or fabricated Actual.

## 5. Task Diff Review

The bounded P7-02 review range is
`fbac85b49b020a356554ab0e5540b8028ce5862f..3a267196d11921ba1111a0774f5f85bd8647ed9f`:
`63` files, `17,180` insertions and `348` deletions across `17` task commits.
Every committed path is inside the frozen P7-02 manifest and belongs to one of
its four checkpoints, direct evidence, generated trilingual catalogs, reviewed
Linux visuals or an evidence-proved runtime repair. No user-owned dirty file,
Darwin snapshot, local report or untracked development prerequisite is in the
range.

The final runtime repair respects Frappe storage ownership: the original
business filename remains in the evidence contract, while the repository
validates Frappe's safe stored filename and exact `Content-Disposition` rather
than demanding storage-name equality. Byte SHA/size/MIME, Frappe content hash,
privacy, scan state and released lifecycle checks remain mandatory. Canonical
reference ordering closes cross-process idempotency without changing public
semantics.

## 6. Security, migration, rollback and limitations

- Project authority precedes Round, lock, Actual, Sample, document, cavity and
  File resolution; actor, CSRF, predecessor/hash and idempotency are checked for
  every command.
- Generic Desk writes/deletes, unknown fields, altered replays, stale versions,
  unsafe Files and cross-Project identities fail closed.
- Migration is additive/idempotent and the controlled Site passed cumulative
  migrations before and after the Trial execution lifecycle.
- After retained history, rollback disables the independent P7-02 routes and
  workspace and uses reviewed forward repair; it does not delete or rewrite
  immutable inputs, Actuals, Samples, files, evidence, events, receipts or
  audits.
- Machine import, production ERPNext and formal quality/approval policies
  remain scoped holds, not global Hard Blockers.

## 7. Decision and transition

P7-02 passes its Level 2 Task Gate. The six Requirement rows advance only to
the truthful per-row dispositions above. Standing continuous-delivery
authority activates P7-03 only at the bounded Requirement/domain/existing-
capability audit. Product implementation may begin only after that audit
freezes the cavity-defect/action/verification plan and machine-readable scope.
