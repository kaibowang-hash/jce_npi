# P8-02 Checkpoint 3 — Leased Worker and Project Draft Binding

Recorded: `2026-08-16T08:18:00Z`

Decision: `PASS — CHECKPOINT 3; FINAL LEVEL 3 AUTHORIZED`

Exact product implementation:
`6960bd13fc07c99c86744df692ab995eb59d4b3c`

Exact final checkpoint:
`f3f7fba8ed0c59ce958f2ecb7709ea3c5a6b1f39`

Final ordinary pull-request CI:
`31935510653` (`PASS`)

## 1. Bounded outcome

Checkpoint 3 completes only the frozen P8-02 worker and Project-draft slice:

- an operation-specific short worker claims only authenticated version-1
  `pending` Inbox receipts or `processing` receipts whose five-minute lease
  expired; live leases cannot be stolen, every recovery gets a new random claim
  token and bounded recovery considers at most `100` receipts;
- the worker commits the claim before Project work, then locks the exact Inbox
  and source binding, revalidates the raw signed event, frozen policy snapshot,
  enabled non-production profile, tenant and source identity, and classifies
  conflict/superseded/bound truth before any Project command;
- service actor, owner and published template are server-resolved and fail
  closed. The actor must be an enabled internal System User with `NPI API User`;
  business code is the signed source document ID and Project idempotency derives
  only from the server source-key hash;
- the existing NPI-owned Project instantiation service creates at most one
  `draft` Project with the exact template snapshot and two `not_started` Gate
  shells. It creates no submission, Gate review/decision/evidence/transition,
  Work Item, Tooling/Trial mutation, Outbox, outbound request or target effect;
- Project creation, source binding, Inbox result and audit commit in the same
  transaction. A bound source can only replay the exact Project ID; ambiguous
  result commits are never overwritten with optimistic success or failure; and
- the scheduler requeues only the bounded P8-02 pending/expired set with a
  deduplicated operation-specific job. It exposes no generic retry, payload
  editing, DLQ movement, manual replay or reconciliation operation.

The runtime-only profile and secret resolvers are inert unless both the fixed
disposable-Site marker and explicit process environment are present. They
install no production endpoint, credential, profile, policy, key, owner,
template or business row and make no ERPNext/JCE call.

## 2. Diagnostic CI and bounded forward repair

Diagnostic ordinary CI `31935393383` ran at exact product commit
`6960bd13fc07c99c86744df692ab995eb59d4b3c`. Repository job `95136346988`
passed the complete repository suite. Secret job `95136346931` stopped before
Gitleaks because current-task verification correctly rejected one changed
historical P8-01 runtime-test path; the later frontend and visual jobs were
cancelled when the repair SHA was pushed.

Forward repair `f3f7fba` restores the historical P8-01 test unchanged and
retains its prior scope, predecessor and artifact labels as comments in the
cumulative CI job, matching the existing P5-P7 preservation pattern. The new
P8-02 runtime test remains the sole assertion of the P8-02 cumulative scope.
No product code, runtime behavior, visual baseline, threshold, tolerance or
PASS criterion changed.

## 3. Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `inbound_project/worker.py` | claim-before-work commit, final/retryable failure, ambiguous result commit, operation-specific recovery and deduplicated short jobs |
| `inbound_project/worker_repository.py` | live/expired lease, raw receipt/policy/profile validation, source order/conflict, actor/owner/template authority, source-derived idempotency, one draft/binding/result/audit transaction |
| Inbox controller and translations | closed pending/processing/terminal state shapes, same-token completion, expired reclaim chronology, terminal immutability, direct `zh`/`zh-TW` coverage |
| runtime-only fixture, verifier and shell | default disable, bad/stale signature, key rotation, concurrent replay, equal conflict, higher-before-older, lease recovery, one draft/two Gates, later-version no rewrite, cross-process stability and redaction |
| CI cumulative lane | retained predecessor contracts plus `p5-01-through-p8-02` runtime scope and `p8-integration-runtime` artifact |
| focused Phase 8 tests | pure domain/metadata/ingress/repository/worker/runtime regressions and explicit no-production/no-generic-operation assertions |

## 4. Local Level 1 and Task Gate evidence

- Complete affected Phase 8 suite: `97/97 PASS`.
- Full local repository Task Gate: `2,026/2,026 PASS`; six pre-existing
  untracked local-prerequisite tests explain the difference from the clean CI
  count. Current-task, V1.2 reconciliation, prototype approval and P0 visual
  governance checks pass.
- Exact Node `24.18.0` generation and direct-language audit pass. The catalog
  reports `7,715` literal English sources with `100%` direct `zh`/`zh-TW`
  coverage; focused i18n tests pass `23/23`.
- Python compile, shell syntax, Task Diff Review, `git diff --check` and the
  staged checkpoint patch Gitleaks scan pass. No `ignore_permissions`, raw SQL,
  TODO/FIXME, production host/credential or target client occurs in the new
  worker/runtime boundary.
- The checkpoint range
  `8ef832699110e4ae6c9316ef86cf5812c28a7bc8..f3f7fba8ed0c59ce958f2ecb7709ea3c5a6b1f39`
  contains `18` files,
  `2,723` insertions and `18` deletions. Existing unrelated dirty documentation,
  evidence, public assets, local snapshots and prerequisite files were not
  staged or changed.

## 5. Final exact-SHA ordinary CI

Pull-request run `31935510653` completed successfully at exact head
`f3f7fba8ed0c59ce958f2ecb7709ea3c5a6b1f39`:

- repository `95136660668`: `2,020/2,020` tracked Python tests plus repository,
  prototype, P0 visual-governance and V1.2 reconciliation verification;
- frontend `95136660777`: `60/60` files, `933/933` unit tests, `426/426` E2E,
  `7,715` literal English sources with `100%` direct `zh`/`zh-TW` coverage,
  statements `80.36%`, branches `80.20%`, functions `83.00%`, lines `82.99%`,
  production build and zero vulnerabilities;
- secret `95136660731`: current-task verification accepts `55` cumulative
  committed paths; `23` first-parent task commits and `518` complete branch
  commits contain no leak; and
- visual `95136660747`: the unchanged fixed-Linux matrix passes `119/119`.

Controlled preflight `95138082394` and cumulative runtime `95138082438`
correctly skip because this is ordinary checkpoint CI, not the final Level 3
dispatch.

Visual artifact `9260567884` has digest
`sha256:2c417cf2d93c1783bcb4e462b20ed903b65b3d0b3b51645757123d452b5f42e3`.
Gitleaks artifact `9260515460` has digest
`sha256:6b7d7a45995de3d254a38dee15b63b575e1a4ae1abf1e281089d7006952231b1`.

## 6. Security, rollback and transition

The reviewed worker accepts authority only from the durable authenticated
receipt plus the exact server profile/policy. Source locks and Project
idempotency protect one logical object; terminal rows are immutable; raw body,
signature and secrets are never emitted in responses, audits, diagnostics or
runtime artifacts. No outbound target transport exists in this slice.

Rollback disables only the fixed P8-02 route, enqueue and worker, retains every
Inbox body/hash, claim, conflict, source binding, Project draft, Gate shell and
audit, and uses reviewed forward repair. It never deletes or rebinds a source,
redispatches an old payload, rewrites terminal truth or compensates in ERPNext.

This evidence closes checkpoint 3 only. Standing continuous-delivery authority
activates only the final P8-02 Level 3 Gate: complete exact-SHA repository,
frontend, secret and visual verification plus cumulative disposable-Site
runtime, migrations twice, signed-route disable/recovery, invalid/stale/key-
rotation authentication, duplicate/conflict/reorder/concurrency, expired-claim
restart, exactly one draft/binding/two Gate shells, later-version no rewrite,
redaction, zero target write, zero production traffic and cleanup, followed by
the `release-gate` review. P8-03 and production ERPNext/JCE remain inactive
until that exact-SHA Gate passes.
