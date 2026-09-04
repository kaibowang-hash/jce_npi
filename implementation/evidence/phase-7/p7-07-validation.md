# P7-07 Level 2 Validation — Immutable Released Trial Summary and Controlled Output

Recorded: `2026-08-15T13:58:38Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact final product checkpoint:
`dda9c13a6c3b499347cb96c830de2a034fa61203`

Primary requirements: `FR-PRN-002`, `FR-INT-015` and `FR-TR-008`.

## 1. Outcome

P7-07 delivers the frozen NPI-owned technical foundation for an immutable
Released Trial Summary and its controlled output:

- one stable append-only summary stream per exact Project and Trial Round;
- exact current approved or rejected conclusion-tip eligibility, with
  submitted and reopened conclusions ineligible for new retention;
- complete closed source identities, versions and hashes without latest-value
  substitution, sampling, truncation or caller-owned redaction;
- a bounded URL-free localized-neutral presentation projection;
- linear successor history that preserves the first summary after later
  reopen, redecision and revision;
- exact `released_trial_summary` source-adapter resolution through the reused
  P5-06 immutable snapshot, private File, QR/hash and audited-download
  mechanics; and
- a dense English, Simplified-Chinese and Traditional-Chinese Trial workspace
  with exact history, sources, redaction, authority and controlled-output
  truth.

No P7-07 behavior defines a production form mapping, signer, retention or copy
policy, publishes an external event/projection/receipt, establishes formal
release or customer approval, closes G7, mutates a Gate, Project, Work Item or
Tooling object, contacts ERPNext, or executes a production print policy.

## 2. Requirement trace review

| Requirement | Level 2 disposition | Evidence boundary |
| --- | --- | --- |
| `FR-PRN-002` | `TECHNICAL_VERIFIED_RELEASED_SUMMARY_CONTROLLED_OUTPUT_FOUNDATION_PRODUCTION_FORM_POLICY_HELD` | Exact immutable summary snapshots and controlled PDF output are proven through the reused print mechanics; production mapping, form owner, signer, retention, browser-print claim and numbered-copy policy remain held under `DR-REC-003/004`. |
| `FR-INT-015` | `TECHNICAL_VERIFIED_NPI_SUMMARY_SOURCE_FOUNDATION_EXTERNAL_PROJECTION_HELD` | The NPI-owned source, closed redaction and localized-neutral projection are proven; external event identity, payload, routing, consumer projection, delivery and receipt remain held under `DR-REC-009`. |
| `FR-TR-008` | `TECHNICAL_VERIFIED_IMMUTABLE_RELEASED_SUMMARY_FOUNDATION_FORMAL_RELEASE_HELD` | Exact approved and rejected technical-conclusion summaries are retained without changing conclusion truth; formal release, customer approval, signature, G7 and production acceptance remain held. |

None of these dispositions is production approval, signature, Gate truth,
external delivery or ERP execution authority.

## 3. Exact-SHA ordinary and controlled Gates

Ordinary pull-request CI `31887451908` passed exact SHA `dda9c13`:

- repository `95018720965`: complete repository verification and `1,921`
  tracked Python tests PASS;
- frontend `95018720920`: `58/58` files, `913/913` unit tests and `408/408`
  non-visual E2E tests PASS; `7,439` direct English sources have `100%`
  Simplified- and Traditional-Chinese coverage; aggregate statement, branch,
  function and line coverage is `80.31%/80.25%/82.90%/82.98%`, with zero
  vulnerabilities;
- visual `95018720948`: the complete `115/115` fixed-Linux governed matrix
  PASS; artifact `9247686747` has upload digest
  `sha256:4a6a6dd70de98d54990931f2c1bb71875043125bce14c8a66bbdb42a578851dd`;
  and
- secret scan `95018720949`: `28` pull-request commits and `481` complete-
  branch-history commits PASS with no leak; artifact `9247642162` has upload
  digest
  `sha256:065ee46e6edb09907a581a52a37287f8e6ffbb084df437f85e7790dc2eb15e6d`.

Independent exact-SHA controlled Gate `31887990384` then passed the same SHA:

- controlled preflight `95019975279` verified the exact repository, dispatch
  mode, head SHA and successful required jobs in ordinary run `31887451908`;
- prior-Gate artifact `9247778821` has upload digest
  `sha256:7ca6b2f3bc0611db909284b2a8fba9189ce334780d6e1974cef63d498bed4ea5`;
  its `attestation.json` payload hashes to
  `sha256:c46da796a3ff9394b29fb4fe993069ef539f90cf0bee814d4555af473e8d6439`
  and records the exact pull-request run, SHA and four required ordinary jobs;
- cumulative runtime `95020020601` passed scope `p5-01-through-p7-07` on
  pinned Frappe commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`;
- runtime artifact `9247862817` has upload digest
  `sha256:4bab7b5d83191cad8485cb29b64b7d60309e619301c595483622f072b4c9b2f5`;
  its `result.txt` payload hashes to
  `sha256:e044f3daf92ad4f0d1d9686d5060db411c747df46b02a47fa987254921bb08fd`
  and records `result=PASS`, the exact SHA, Level 2 mode, predecessor scope
  `p5-01-through-p7-06` and final scope `p5-01-through-p7-07`; and
- the always-run cleanup removed the disposable MariaDB/Redis containers,
  volumes and network.

Repeated repository/frontend/visual/secret jobs were skipped by the controlled
dispatch only after fail-closed exact-SHA attestation passed. This is the
P7-07 Level 2 Task Gate. Phase 7, PR and release boundaries still require the
applicable complete Level 3 Gate.

## 4. Controlled truth and negative matrix

The cumulative disposable Site retains exactly two summary revisions, two
sealed summary receipts, two summary audits, one controlled-print snapshot,
one private controlled PDF output and the exact first-output source snapshot.
It also reconciles the cumulative Trial state to `2` Rounds, `18` lifecycle
events, `49` Trial command receipts and `11` conclusion revisions. The runtime
proves:

- the first approved summary remains byte- and hash-stable after reopen,
  redecision and a rejected technical successor;
- the successor binds the exact later Round and conclusion tips, while no-op,
  stale and forked successors fail closed;
- absent streams do not disclose protected secondary identities and commands
  require internal command authority before body parsing;
- the disposable mapping resolves only the exact retained summary revision;
  the private PDF hash and size match its immutable output record;
- same-process and cross-process replay, altered-payload conflict, generic
  CRUD denial, IDOR/no-write, route disable/recovery, migrate-twice and
  transaction rollback preserve retained truth;
- persisted summaries, receipts, audits, controlled snapshots and runtime
  results pass the closed sensitive-key, raw-URL and private-path scans; and
- zero Gate, Project, Work Item, Tooling, Trial-source, production-transition,
  ERP, integration, Outbox, Inbox, provider or external mutation holds.

## 5. Task Diff Review and diagnostic attempts

The bounded P7-07 range is
`b9dc2135e16e1b19d375bb29ab733e5e63ccef08..dda9c13a6c3b499347cb96c830de2a034fa61203`:
`19` commits, `62` paths, `12,394` insertions and `106` deletions. The exact-
SHA current-task guard accepted all committed paths. They belong to the four
frozen checkpoints, direct evidence, generated trilingual catalogs, reviewed
fixed-Linux visuals or bounded controlled-runtime forward fixes. User-owned
dirty files and `implementation/LAST_RUN.md` are outside this closeout.

Nine controlled attempts are retained as diagnostic failures, never PASS
evidence:

- `31879465954` exposed the runtime Administrator-fixture guard;
- `31880413652` exposed cumulative P7-04 review-Round identity drift;
- `31881430363` exposed dash-prefixed disposable encryption-key CLI parsing;
- `31882139299` exposed conclusion selection that was not bound to the exact
  Round tip;
- `31883285579` exposed the unauthorized absent-stream status ordering;
- `31884101755` exposed a no-op probe using the revision identity instead of
  the stable summary-stream identity;
- `31884984877` exposed an unclassified non-increasing successor;
- `31885950651` exposed missing internal command-role enforcement; and
- `31886960724` exposed stale cumulative Trial cardinality expectations.

Every attempt passed exact-SHA ordinary CI before controlled dispatch, failed
closed, retained no accepted runtime PASS result, and ran cleanup. Each bounded
forward fix preserved the Requirement, API, permission, ownership,
transaction, idempotency, audit, redaction and PASS rules, passed affected
tests, and was followed by a new independent exact-SHA ordinary and controlled
attempt.

## 6. Security, migration, rollback and limitations

- Authentication and internal command authority precede body parsing; Project
  authority precedes protected secondary-ID handling; mutations enforce CSRF,
  exact current tips, expected predecessor, hashes and actor-bound idempotency.
- Summary, conclusion, receipt, audit, controlled snapshot/output, access and
  private File history is append-only. Unknown fields, altered replay, stale
  sources, corrupt provenance and cross-Project references fail closed.
- Additive/idempotent migrations and the complete cumulative runtime passed on
  a fresh disposable Site. No production ERPNext credential or connection was
  used.
- Before retained data, rollback may restore the starting controller and a
  fresh disposable Site. After retained history exists, rollback is route and
  Trial-workspace disable plus reviewed forward repair; exact retained history
  is never deleted, edited, renumbered, rehashed or re-rendered.
- Production form/signature/retention/copy policy, formal release/customer/G7
  authority, external event/projection/receipt and ERP/JCE production
  execution remain explicit scoped holds under `DR-REC-003/004/009`.

## 7. Decision and transition

P7-07 passes its Level 2 Task Gate with the three truthful held dispositions
in section 2. The evidence-based task review records `P0=0` and `P1=0`; this
review does not replace the required Level 3 workflow at a Phase, PR or release
boundary.

Standing continuous-delivery authority activates only the bounded P7-08
Requirement/domain/existing-capability audit for `UX-020`. Product code may
begin only after that audit freezes the responsive Trial/Gate review, same-BFF
capability, photo-evidence, issue-capture and scan-entry boundary. Mobile grants
no new authority, and complex engineering tables remain desktop-only.
