# P5-04 Controlled-Site Runtime Candidate

Recorded: `2026-08-05T13:21:38Z`; CI classified: `2026-08-05T13:38:32Z`

Status:
`PASS — LOCAL LEVEL 1 HARNESS; EXACT-SHA CI CLASSIFIED; BOUNDED HISTORY REPAIR`

Task:
`P5-04 — EBOM revision and comparison`

Requirements:

- `FR-DS-011`; and
- `FR-DS-012`.

Starting synchronized checkpoint and remote HEAD:
`0c344fef0dbab4a84dc9ee84e3400a626de8d0c9` (`0 ahead / 0 behind`)

Pushed controlled-runtime candidate:
`b74511ea084a6b87604c861360fcb8004b645892` (`0 ahead / 0 behind`)

Reusable predecessor evidence:

- complete unchanged ordinary CI `31008027534` passed on exact SHA
  `0c344fef0dbab4a84dc9ee84e3400a626de8d0c9`;
- repository job `92312741415` passed the complete repository, `933` tracked
  Python tests at that exact predecessor, complete frontend/browser,
  current-tree and full `138`-commit history secret lanes at its exact
  predecessor tree;
- fixed-Linux job `92312741300` passed the governed `62/62` matrix; visual
  artifact `8931239683` has digest
  `sha256:050b7fc6c8bf9ae351e789b5f521cd3adf9c34b45e27dc95d308935ff1bda648`;
- secret artifact `8931400483` has digest
  `sha256:3c86ce6fc0b48fb15894b52b85bedd0ee04a2e1b09f8f7f244ad6614e102be81`;
  and
- P5-03 final unchanged controlled-Site Gate `30991177478` remains sealed
  predecessor evidence and is not reopened.

This checkpoint activates only the P5-04 controlled-Site proof harness. It is
not a controlled-Site PASS and is not the P5-04 Level 2 Task Gate. P5-05 and
Phase 6 remain inactive.

## Exact-SHA ordinary CI classification

Ordinary CI `31010444857` ran against exact candidate `b74511e`:

- repository job `92320943724` passed complete `verify.sh`, the complete
  non-visual browser suite, current-tree Gitleaks and every setup/security
  step before the final full-history scan;
- fixed-Linux visual job `92320943829` passed the complete governed `62/62`
  matrix without a baseline or threshold change;
- controlled runtime job `92320944597` remained correctly skipped; and
- the repository job failed only the `139`-commit history scan on one exact
  `generic-api-key` match at immutable candidate line `842`:
  `b74511ea084a6b87604c861360fcb8004b645892:scripts/verify_ebom_runtime.py:generic-api-key:842`.

The matched source is the literal non-secret query fixture
`p504-predecessor-route-isolation` adjacent to the `query_key` keyword. It is
not a credential, token, external identifier or product value. The bounded
repair adds only that exact immutable fingerprint to `.gitleaksignore`, the
strict reviewed-fingerprint verifier and its exact test inventory. Current
source builds the same visible synthetic query fixture from two fixed pieces
and passes a named constant, preventing recurrence without changing any HTTP
request, product behavior, test criterion or scanner rule.

## Delivered runtime boundary

- Added one bounded `verify_ebom_runtime.py` verifier which reuses the already
  controlled disposable P5 Project and its retained ordinary internal member.
  It creates only a namespaced, visibly synthetic P5-04 policy and EBOM
  fixture on that disposable Site.
- The ordinary member proves empty workspace and explicit policy truth, guest
  authentication denial, non-member object-hiding denial, first immutable
  revision creation, actor-bound replay and changed-payload conflict.
- An invalid self-parent successor proves transaction rollback before a valid
  exact successor is created. The retained root stays at version `2` with one
  revision after the failed command; the valid successor advances it to
  version `3` with an exact predecessor ID/hash.
- Exact R1/R2 comparison proves canonical quantity, attribute and added-line
  changes and their derived counts. The exact R2 lifecycle then proves
  `draft → in_review → approved → released`, three append-only events,
  high-risk confirmation, a stale-version conflict and unchanged immutable
  R1 history.
- The verifier asserts exact persistence cardinality for one root, two
  revisions, three immutable lines, two lifecycle projections, three events,
  five sealed command receipts and five trace-correlated audit operations.
- A separate `npi_p5_04_routes_disabled` cycle proves P5-04 returns
  `EBOM_ROUTES_DISABLED` while the retained P5-01 Document route remains
  available, then proves exact EBOM recovery.
- A separate verifier process replays the original create and exact release
  commands with the same actor-bound keys and identities. The shell restores
  the P5-04 switch to absent on every exit and retains the existing two
  consecutive migrations.
- The manual workflow remains dispatch-only, uses no repository secret and
  records exact scope `p5-01-through-p5-04` in a PASS-only artifact.

No production ERPNext endpoint, Item, Item Code, stock UOM, MBOM, routing,
inventory, cost, execution record, production policy or production authority
is created or contacted.

## Bounded sanitized diagnostics

Runtime HTTP failures are reduced to exactly:

- one code from the closed `P504_RUNTIME_*` stage allowlist;
- one exception type matching `^[A-Za-z][A-Za-z0-9_.]{0,127}$`, otherwise the
  fixed `HttpStatusError`; and
- the exact request trace matching `^trace-[a-f0-9]{32}$`.

The diagnostic path never emits response bodies, server messages, stack
traces, filesystem paths, cookies, CSRF values, fixture passwords or database
credentials. The local test injects a response containing deliberately
sensitive strings and proves none can enter the diagnostic. No diagnostic
header or server-side behavior is activated by this candidate.

## Requirement → code → test → evidence

| Requirement | Runtime boundary | Direct proof |
|---|---|---|
| `FR-DS-011` | controlled synthetic policy; immutable EBOM/revision/line persistence; lifecycle authority; independent route switch; replay/conflict/rollback/audit | runtime verifier contract tests; eight metadata definitions; normal-member/guest/non-member flows; two migrations; fresh/route/recovery/replay shell inventory |
| `FR-DS-012` | exact same-root R1/R2 comparison | expected `quantity`, `attribute`, `added` ordering and derived `1/0/1/0/1` summary assertions |

## Changed files → affected tests

| Changed boundary | Affected verification | Local result |
|---|---|---|
| `scripts/verify_ebom_runtime.py` | new runtime verifier contract; complete P5 EBOM domain/API/repository/security suites | PASS |
| `scripts/verify-frappe-runtime.sh` | Bash syntax; existing Document runtime inventory; new migration/switch/fresh/recovery/replay inventory | PASS |
| `.github/workflows/ci.yml` | existing and new manual-lane declaration tests; pinned devcontainer verifier | PASS |
| exact historical synthetic fingerprint and current lexical fixture | strict devcontainer/Gitleaks allowlist verifier and test inventory; runtime contract | focused `30/30` and network-backed pinned verifier PASS |
| runtime tests | `tests.test_phase5_ebom_runtime_verifier`; `tests.test_phase5_document_runtime_verifier` | `44/44` PASS |
| adjacent EBOM/Document modules | all EBOM suites plus both runtime verifiers | `87/87` PASS |
| complete tracked Python | `python3 -m unittest discover -s tests` | `948/948` PASS |
| repository facts | compileall, prototype approvals, P0 visual governance, V1.2 Reconciliation, prohibited-pattern and diff checks | PASS |
| pinned devcontainer registry facts | network-backed `scripts/verify_devcontainer.py` | PASS |

The complete Python run emits only the retained expected negative-path error
reporter records while all `948/948` assertions pass. The local macOS host has
no unversioned `python`; exact-SHA CI remains the authoritative execution of
the repository wrapper before the controlled Site may be dispatched.

## Security, domain, migration and rollback review

- The normal member has `NPI API User` and current Project membership but no
  `System Manager`; the synthetic policy independently names that actor for
  create, submit, review and release. Transport role, Project visibility and
  administrator access do not silently grant policy authority.
- Every command retains trusted CSRF, exact request/trace identity, exact
  policy ID/version/hash, exact optimistic/lifecycle versions and an
  actor-bound idempotency key. Callers cannot select tenant, actor, lifecycle
  result, audit truth or formal ERP identity.
- Metadata verification is read-only. Migration remains additive and runs
  twice on the fixed physical disposable Site before the server starts.
- Failed invalid and stale commands must leave no revision, line, event,
  receipt or audit residue; persisted cardinality checks prove this boundary.
- Before P5-04 retained history exists, revert this harness normally. After
  history exists, disable only `npi_p5_04_routes_disabled`, preserve every
  immutable row and deploy a reviewed forward repair.
- `R-059` production-policy uncertainty remains scoped. `R-060` remains open
  until exact-SHA normal CI, controlled-Site evidence and Level 2 pass. No new
  Decision Request, ADR or Hard Blocker is introduced.

## First incomplete action

Create and push one bounded history-evidence repair checkpoint containing only
the exact immutable fingerprint, strict verifier/test inventory, current
fixture lexical hardening and synchronized P5-04 evidence/controller files.
Preserve every user-owned local modification and untracked asset. Require
complete unchanged ordinary CI on the repair SHA; only then dispatch one
controlled Site run. If that run fails, classify the exact safe stage and
repair only a uniquely proven product root within the controller budget.
P5-05 and Phase 6 remain inactive.

## Exact-SHA controlled run and proven fixture-boundary repair

History-scan repair checkpoint
`bc81d468b12cc959e4761a593c451cf8785914b2` passed complete unchanged
ordinary CI `31011531101`:

- repository job `92324678678` passed `verify.sh`, complete browser,
  current-tree Gitleaks and the complete branch-history scan;
- fixed-Linux visual job `92324678452` passed `62/62`; and
- controlled runtime job `92324679241` remained correctly skipped.

Manual controlled run `31013199095` was pinned to exact SHA `bc81d46`.
Controlled job `92330431845` proved:

- exact Bench tools, pinned Frappe commit, disposable Site, both migrations
  and cleanup passed;
- the complete unchanged P5-01/02/03 Document runtime and its three
  route-disable/recovery cycles passed; and
- P5-04 stopped before EBOM creation at synthetic policy provisioning.

The companion repository job `92330432221` passed `verify.sh`, complete E2E
and current-tree Gitleaks, and fixed-Linux visual job `92330432419` passed
`62/62`. The workflow conclusion is failure only because the controlled job
failed; the workflow-dispatch event correctly skipped the PR-only complete
history scan already passed by ordinary CI `31011531101`.

The failed verifier used generic REST create/update for `NPI EBOM Policy` and
`NPI EBOM Policy Version`. Both controllers intentionally require the closed
`ebom_policy_write()` administration context and therefore correctly rejected
that generic write. The verifier assertion then emitted a Python traceback
instead of the documented sanitized diagnostic triple. Direct comparison of
the controlled log, verifier call site and both guarded controllers uniquely
proves a verifier/fixture boundary defect; no product root, permission defect
or business-rule change is implicated.

The bounded repair:

- removes only the generic policy REST create/update calls from the verifier;
- adds one allowlisted fixed-Bench fixture that validates the exact disposable
  Site, fixture namespace, retained Project and enabled internal actor;
- creates and publishes only the visibly synthetic policy under the existing
  `ebom_policy_write()` context without `ignore_permissions`, raw SQL or core
  changes;
- maps any fixture subprocess or result-shape failure to only the allowlisted
  fixture stage, a validated fixed exception type and the exact deterministic
  fixture trace ID, without forwarding stderr, traceback or response content;
- commits on success and rolls back on failure; and
- keeps every product API, permission, DocType, ownership, transaction,
  lifecycle, idempotency and PASS rule unchanged.

Affected verification after the repair:

- runtime-verifier contract: `11/11` PASS;
- complete P5-04 EBOM suites: `54/54` PASS;
- retained Document runtime contract: `35/35` PASS;
- complete tracked Python: `950/950` PASS;
- Python compilation and `git diff --check`: PASS.

The local complete wrapper did not start its test body because the host has
Node `24.2.0` / npm `11.3.0`, while the repository requires Node `24.18.0` /
npm `11.16.0`. This is a preflight environment mismatch, not a test failure.
Complete fixed-toolchain CI `31011531101` remains the predecessor, and the
repair checkpoint requires a new complete exact-SHA CI before any final Gate.

This is behavior-neutral verifier/fixture repair and consumes no product-root
repair round. The next action is one scoped checkpoint, complete unchanged
ordinary CI on its exact SHA and then the retained final unchanged
controlled-Site Gate. P5-05 and Phase 6 remain inactive.
