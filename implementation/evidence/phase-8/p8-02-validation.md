# P8-02 Level 3 Validation — Signed Webhook and Inbox Project Draft

Recorded: `2026-08-16T12:05:00Z`

Decision: `PASS — LEVEL 3 TASK GATE`

Exact final product checkpoint:
`260ed2ef865180f33edfca0e8fe1daf4a0a4e771`

Primary requirements: `INT-002`, `FR-PM-002`

## 1. Outcome

P8-02 delivers the frozen default-disabled inbound Project-draft slice:

- one fixed POST boundary authenticates the exact method, path, key ID,
  timestamp, request ID and raw bytes with HMAC-SHA256 before JSON trust;
- a fixed five-minute replay window, overlapping server-owned key rotation,
  duplicate-key-free closed Quotation/Sales Order submit events and bounded
  request media/size/encoding rules fail closed;
- an immutable Inbox receipt, exact event/hash identity, source-document head
  and structural audit commit before `202`, while enqueue happens only after
  commit and long Project work never runs in the webhook request;
- a bounded worker claims pending or expired-processing receipts without
  stealing a live lease, revalidates frozen profile/policy/source truth and
  serializes the exact source binding;
- server-owned tenant, actor, owner, template, Project type and source-derived
  idempotency create at most one NPI-owned draft through the existing Project
  aggregate, retaining its exact template snapshot and two Gate shells; and
- duplicate, conflict, reorder, concurrency, restart and later-version truth
  remain durable without Project submission, rewrite or downstream effect.

P8-02 installs no source profile, signing key, secret, owner/template mapping,
production endpoint or production data. It sends no target write, performs no
cross-database access and does not contact production ERPNext or JCE Core.

## 2. Checkpoint evidence

| Checkpoint | Result | Durable evidence |
|---|---|---|
| pure signature/event/configuration domains, contracts and metadata | `PASS` at `a040f21d4379d529f9524bbf09c1ac5016fe6881` | `implementation/evidence/phase-8/p8-02-domain-metadata-checkpoint.md` |
| fixed signed ingress and durable landing | `PASS` at `4c77c4472a0ea07bc14a2073f0b6c7d3b006b870` | `implementation/evidence/phase-8/p8-02-ingress-landing-checkpoint.md` |
| leased worker and at-most-one Project binding | `PASS` at `f3f7fba8ed0c59ce958f2ecb7709ea3c5a6b1f39` | `implementation/evidence/phase-8/p8-02-worker-project-checkpoint.md` |
| cumulative disposable runtime and bounded forward repairs | `PASS` at `260ed2ef865180f33edfca0e8fe1daf4a0a4e771` | exact-SHA ordinary and Level 3 runs below |

The post-checkpoint-3 chain preserved the frozen API, ownership, permissions,
transaction order and PASS criteria. It repaired two product roots and three
verifier/fixture roots, always through a new exact-SHA ordinary Gate before the
next controlled run:

- `31936906558` exposed that Guest could not persist the already-authorized
  ingress rows; `ecac118` added a guarded internal Administrator service scope,
  retained all controller checks and restored the original caller;
- `31938675345` exposed an incomplete retained-user create response;
  `9b7f7c3` made the verifier read the durable user before asserting it;
- `31940189741` exposed a fixture user without Desk access; `c479882` grants
  only Desk User plus NPI API User and never grants System Manager;
- `31941719602` exposed Frappe field-unique races as
  `UniqueValidationError`; `b503980` classifies that peer unique failure with
  `DuplicateEntryError`, rolls back and performs one bounded durable replay
  classification; and
- `31943330103` sampled its digest before a legitimate later v3 receipt;
  `260ed2e` captures the final retained context after all three receipts and
  compares replay against that final durable truth.

None of the diagnostic failures produced a PASS artifact. The two product
repairs are covered by focused unique-race and permission tests; the other
three corrections are verifier/fixture-only.

## 3. Exact-SHA ordinary Gate

Pull-request workflow `31944345420` passed at the exact final SHA:

- repository `95157995410`: `2,021/2,021` tracked Python tests and repository,
  current-task and reconciliation verification PASS;
- frontend `95157995356`: `60/60` files, `933/933` unit tests and `426/426`
  non-visual E2E PASS; coverage is `80.36%` statements, `80.20%` branches,
  `83.00%` functions and `82.99%` lines; all `7,715` literal English sources
  have direct `zh` and `zh-TW` translations; build and vulnerability audits
  PASS with zero findings;
- secret `95157995393`: `24` first-parent task commits and `524` complete
  branch commits contain no leak; artifact `9262871812`, digest
  `sha256:714e67d2e42a0dbc56906f706ebe6400ca2ef2d93cd66fbfe91d331454fbcf25`;
  and
- visual `95157995395`: the complete governed fixed-Linux matrix passes
  `119/119`; artifact `9262918058`, digest
  `sha256:a30c32289e92f6fd226fd48b915fc10735691c1ff87e466b6e5b6719f82226b8`.

The host worktree is intentionally not cited for the production brand audit:
an unrelated user-owned untracked image under `frontend/public/` trips that
guard. It was not staged, changed or used as PASS evidence.

## 4. Final cumulative Level 3 Gate

Workflow `31944941030` passed every Level 3 lane at the unchanged exact SHA:

- repository `95159399250`: `2,021/2,021` tracked Python tests and complete
  repository verification PASS;
- frontend `95159399214`: complete unit, E2E, translation, coverage, build and
  vulnerability verification PASS;
- secret `95159399232`: current-tree Gitleaks scans `525` commits with zero
  results; artifact `9263019006`, digest
  `sha256:5dafe0046ab32eb3cd5323b2d1ca1e55b8342b450ab8c541a007e789c3bfc97b`;
- visual `95159399354`: `119/119` PASS; artifact `9263064542`, digest
  `sha256:0da75f3c4fc1e216936affd7b03910a9f2572246839db2b3ff391f498fe09403`;
- controlled preflight `95160725595`: exact-SHA, current-task and Gate-mode
  checks PASS; and
- cumulative disposable runtime `95160766683`: P5 through P7-07 plus P8-01
  projections and P8-02 inbound Project runtime PASS in `7m47s`.

Runtime artifact `9263250125` has digest
`sha256:f9a8acee24ee8ac6d07c8e0efddd2cc384f1664fbd9397a7c3a219c59dc3b693`.
Its result file hashes to
`sha256:531df14622f6db42a5602586a4eb65760a8c8837b0382990bc0708fdc278b67d`
and records `result=PASS`, exact head SHA, `gate_mode=level_3`, disposable Site
`npi.localhost`, database `npi_one_runtime`, scope `p5-01-through-p8-02`,
pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1` and command
`bash scripts/verify-frappe-runtime.sh --projection-only`.

## 5. Runtime truth and fault closure

The controlled Site proves three exact P8-02 summaries:

- default-disabled: `claimRecovery=false`, `projectCount=0`,
  `replayStable=false`;
- fresh signed processing with concurrent unique-race recovery:
  `claimRecovery=true`, `projectCount=1`, `replayStable=false`; and
- separate-process replay: `claimRecovery=true`, `projectCount=1`,
  `replayStable=true`, with the same final result digest as the fresh state.

The cumulative verifier also proves:

- bad and stale signatures reject before business parsing; the prior and
  active non-production keys overlap only within the fixed window;
- exact event replay is stable, different-payload event reuse conflicts,
  older source versions remain superseded, equal versions with different
  content conflict, and a later version after creation cannot rewrite the
  Project or binding;
- a live claim is not stolen, an expired claim is recovered and concurrent
  event IDs for one source converge to one draft Project, one source binding,
  one frozen template snapshot and two `not_started` Gate shells;
- the retained Inbox contains three distinct receipt UUIDs and cross-process
  replay changes no durable Inbox, binding, Project, Gate-shell or audit truth;
- unauthorized and invalid states fail closed with stable problems and
  request/trace identity, while raw signed bytes, signature, key, secret,
  Authorization, cookie, Site path, database detail and traceback are not
  logged or returned;
- application migrations run twice after initial Site setup; and
- only loopback traffic is used, zero target request/write and zero production
  traffic occur, and the disposable MariaDB/Redis containers, volumes and
  network are removed.

## 6. Requirement and release disposition

The release review covers raw-request authentication, shared event/OpenAPI and
ownership contracts, additive Inbox/source-binding DocTypes, ingress,
repository, worker, existing Project aggregate reuse, permissions, audit,
i18n, migration, rollback, runtime, secrets and complete visual regression.
It finds no P0, P1 or P2 issue and accepts P8-02 at Level 3.

`INT-002` and `FR-PM-002` advance only for the technically verified signed-
webhook, durable Inbox and at-most-one Project-draft foundation. Production
ERPNext webhook acceptance, production profile/key/owner/template mapping and
operational reconciliation remain held. `NFR-INT-001` full retry/DLQ/manual
replay/reconciliation remains P8-07. P8-02 does not satisfy Item, MBOM, Asset
or quality target execution.

Task Diff Review over `b938926..260ed2e` covers `14` commits, `56` files,
`9,589` additions and `188` deletions. Changed files map directly to domain,
contract, metadata, ingress, repository, worker, Project aggregate, i18n,
controlled runtime and focused concurrency/security tests. No accepted-path
TODO, FIXME, fake success, test deletion or threshold reduction remains.

## 7. Rollback and transition

Before retained use, the independent P8-02 route, metadata and worker may
return to the P8-01 checkpoint. After any Inbox receipt, source binding,
Project or audit exists, rollback disables only the fixed ingress, enqueue and
worker, retains every raw body/hash, claim, conflict, binding, Project draft,
Gate shell and audit, and deploys a reviewed forward repair. It never deletes,
rebinds, redispatches, rewrites history or compensates in ERPNext.

P8-02 passes Level 3. Standing continuous-delivery authority may activate only
the bounded `P8-03 — Item publish execution` requirement/domain/existing-
capability and security audit. P8-03 product behavior waits for its frozen
plan and exact-SHA ordinary CI. Production ERPNext/JCE contact and P8-04
through P8-09 remain prohibited.
