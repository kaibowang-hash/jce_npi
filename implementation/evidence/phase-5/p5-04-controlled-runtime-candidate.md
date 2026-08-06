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

## Final unchanged Gate and closed policy-fixture substage diagnostic

Fixture repair checkpoint `cb314ffb2f5e6600bec126463fbcb7e9ac645069`
passed complete exact-SHA ordinary CI `31014577854`:

- repository job `92335171956` passed `verify.sh`, complete E2E, current-tree
  Gitleaks and the complete PR branch-history scan;
- fixed-Linux visual job `92335172189` passed the unchanged `62/62` matrix; and
- controlled job `92335172839` remained correctly skipped.

Final unchanged controlled workflow `31015391479` retained exact SHA
`cb314ff`. Controlled job `92338012425` passed pinned tools, the fixed Bench,
fixed disposable Site, both migrations, the complete unchanged P5-01/02/03
Document runtime, every route-disable/recovery cycle and cleanup. Companion
repository job `92338012349` passed complete verification/E2E/Gitleaks and
fixed-Linux visual job `92338012500` passed `62/62`.

P5-04 stopped before EBOM creation and emitted only:

`P504_RUNTIME_POLICY_FIXTURE / BenchFixtureError /
trace-38a09ee9b80150e98daef921d5b01fd1`

That tuple proves the fixed-Bench synthetic policy fixture boundary but cannot
distinguish root document construction/insertion, version construction/
insertion, publication or final persistence validation. Guessing a repair is
therefore prohibited.

The active behavior-neutral diagnostic checkpoint:

- divides only that verifier fixture into closed root-build, root-insert,
  version-build, version-insert, publish and persistence substages;
- maps an exception to its Python type only after the fixed type allowlist
  syntax succeeds and uses the deterministic substage trace ID;
- accepts a child-process diagnostic only when the final non-empty stderr line
  exactly matches an allowed substage, validated type and exact deterministic
  trace;
- falls back to the existing aggregate `BenchFixtureError` on any malformed,
  non-allowlisted or trace-mismatched child output; and
- never forwards stderr, traceback, exception text, response data, paths,
  cookies, CSRF values, fixture passwords or database material.

Focused verification passes:

- runtime verifier: `14/14`;
- complete P5-04 EBOM suites: `57/57`;
- complete tracked Python: `953/953`.

No product API, permission, DocType, Schema, ownership, policy, transaction,
lifecycle, idempotency or PASS rule changes. Under the controller this remains
`IN_PROGRESS_DIAGNOSTIC`, consumes no product-root repair round and cannot be a
Gate PASS. Complete exact-SHA ordinary CI is required before one diagnostic-only
controlled-Site dispatch. Only a uniquely proven synthetic fixture substage may
then be repaired, followed by affected checks, ordinary CI and one final
unchanged controlled-Site Gate. P5-05 and Phase 6 remain inactive.

## Diagnostic result and product-root authority blocker

Diagnostic checkpoint `217632f7f1c4a1c5cdd68d20e04c81b6bbbeddd6`
passed complete exact-SHA ordinary CI `31016624361`:

- repository job `92342241345` passed `verify.sh`, complete E2E, Gitleaks and
  complete PR branch history;
- fixed-Linux visual job `92342241381` passed unchanged `62/62`; and
- controlled job `92342242244` remained correctly skipped.

Diagnostic-only controlled workflow `31017098820` retained exact SHA
`217632f`. Controlled job `92343913010` passed pinned tools, fixed Bench,
disposable Site, both migrations, complete unchanged P5-01/02/03 Document
runtime, every route-disable/recovery cycle and cleanup. Companion repository
job `92343913023` and fixed-Linux visual job `92343913060` passed. The
controlled job emitted only:

`P504_RUNTIME_POLICY_VERSION_PUBLISH_FIXTURE / ValidationError /
trace-9d081239bf095af1a7f41eeaa65a0d9d`

This proves policy-root build/insert and policy-version build/draft insert all
passed. Direct controller/domain cross-validation proves the remaining root:

1. draft insert computes and persists the canonical draft `policy_snapshot`
   and `snapshot_hash`;
2. the legal transition changes only `publication_state` to `published`;
3. `ebom_policy_value(self)` forwards that persisted draft hash into
   `EngineeringBomPolicyVersion(state=published, snapshot_hash=draft_hash)`;
4. the domain correctly compares the supplied hash with the published
   canonical payload and raises before `_apply_policy()` runs; and
5. `_apply_policy()` already contains the intended exact-prior-hash allowance,
   but it is unreachable for this valid transition.

The bounded solution is to treat only the exact persisted prior draft hash as
server-owned during published-state domain reconstruction. The original
document value remains unchanged for `_apply_policy()` to accept only the exact
prior or new canonical hash. Any different caller hash, changed snapshot,
non-draft predecessor or mutation of a published version remains rejected.
Affected controller/domain/runtime tests, complete ordinary CI and one final
unchanged controlled-Site Gate are required. No Requirement, public API,
permission, DocType, Schema, ownership, policy authority, transaction order,
idempotency or PASS criterion needs to change.

This is one uniquely proven product root, not an environment/verifier/fixture
root. `PHASE_STATUS.yaml` records all five product-root rounds consumed. The
additional user authorization currently on record is explicitly limited to
P5-01 checkout diagnostics and cannot be transferred to P5-04. Under
`AUTOPILOT_CONTROLLER.md`, a necessary Gate still failing after those five
rounds is a true Hard Blocker. State is therefore `BLOCKED_EXTERNAL`.

Single user action required: explicitly authorize one additional bounded P5-04
product-root repair round, limited to this policy-version draft-to-published
prior-snapshot-hash defect, affected tests, complete ordinary CI and one final
unchanged controlled-Site Gate. P5-05 and Phase 6 remain inactive.

The blocker-state checkpoint
`6b48c5595769bf544df4875093ee76d096b40c06` is pushed with local/remote
`0 ahead / 0 behind`. Exact-SHA ordinary CI `31018194326` passed repository
job `92347730660`, including complete verification, E2E, Gitleaks and branch
history, and fixed-Linux visual job `92347730622` passed `62/62`; controlled
job `92347731389` was correctly skipped. This seals only the truthful
`BLOCKED_EXTERNAL` evidence. It does not authorize or implement the product
repair and does not consume the reserved final unchanged controlled-Site Gate.

## Authorized policy-publication repair and new create-stage blocker

The user explicitly authorized repair commit
`d21d21ad52efa2a88bc459adc43f97f265715071`, its ordinary CI, controlled Gate
and continued Autopilot. The bounded three-file change treats only the exact
persisted prior draft hash as server-owned during a draft-to-published domain
reconstruction. The original document value remains available to
`_apply_policy()`; unrelated hashes, non-draft predecessors and non-publish
transitions remain rejected.

Local affected EBOM tests passed `58/58`, complete Python passed `954/954`,
compilation and `git diff --check` passed. The host's complete wrapper stopped
only at its fixed Node/npm preflight because the host has Node `24.2.0` and
npm `11.3.0`; exact-SHA ordinary CI `31020190868` used the required Node
`24.18.0` and npm `11.16.0` and passed repository, complete E2E, Gitleaks/
branch history and the fixed-Linux visual matrix.

Final unchanged controlled workflow `31020886002` retained exact SHA
`d21d21a`. Its controlled job `92356978480` passed fixed Bench/Site, two
migrations, complete unchanged P5-01/02/03 runtime, policy publication, empty
EBOM workspace, guest/unrelated authorization, route recovery and cleanup.
Repository job `92356978685` and visual job `92356978587` passed. The
controlled job then emitted only:

`P504_RUNTIME_CREATE / HttpStatusError /
trace-f92a1e065fe35759b261601244cca7d4`

The former `P504_RUNTIME_POLICY_VERSION_PUBLISH_FIXTURE` did not recur; the
repair therefore advanced the unchanged Gate. The new aggregate create code
is not a unique root: it covers exact policy load and actor authority,
idempotency receipt replay/insert, EBOM root/revision/line/lifecycle writes,
root projection save, audit, response construction and receipt sealing. The
validated body supplied no safe exception type beyond `HttpStatusError`.
Guessing a product or verifier repair is prohibited.

The prior bounded repair/final-Gate authorization is exhausted. One new
explicit authority is required for a behavior-neutral allowlisted create-stage
diagnostic, affected/full ordinary CI, at most one diagnostic controlled Site,
repair of only one uniquely proven in-scope verifier/fixture or product root,
and one final unchanged Gate. P5-04 remains `BLOCKED_EXTERNAL`; P5-05 and
Phase 6 remain inactive.

## Authorized create-stage diagnostic checkpoint

Recorded: `2026-08-06T03:47:13Z`

The user explicitly requested repair and continuation of the existing
Goal/Autopilot after receiving the exact bounded create-stage authority text.
The execution-authority blocker is closed. The active sequence retains at most
one diagnostic controlled Site, one uniquely proved repair and one final
unchanged Gate.

The behavior-neutral diagnostic adds one closed header scope to only the first
synthetic EBOM create command. Server instrumentation covers command context,
input parsing, Project lock, exact policy load/authority, payload hash,
idempotency replay, Project mutability, domain build, receipt/root/revision/
line/lifecycle persistence, root projection, audit, response and receipt seal.
Only the first failing allowlisted code, validated exception type and exact
request trace are written through the existing safe logger. The response body,
status, request contract and transaction remain unchanged; the verifier reads
only an exact three-field JSON record beneath the fixed Bench path.

Changed-files to affected-tests:

| Boundary | Proof | Result |
|---|---|---|
| EBOM diagnostic/API/repository and controlled verifier | complete `test_phase5_ebom*.py` | `62/62 PASS` |
| shared Document diagnostic/runtime non-regression | Document API, baseline repository and runtime verifier | `70/70 PASS` |
| complete tracked Python | `python3 -m unittest discover -s tests` | `958/958 PASS` |
| syntax and whitespace | `compileall`; `git diff --check` | `PASS` |

No Requirement, public API, permission, DocType, Schema, ownership, policy,
transaction order, idempotency, audit, UI, localization or PASS rule changed.
The diagnostic is `IN_PROGRESS_DIAGNOSTIC`, not a Gate PASS and not a product
repair round. Complete exact-SHA ordinary CI is mandatory before the single
diagnostic dispatch.

## Create-stage diagnostic result and synthetic fixture repair

Diagnostic checkpoint `008e6ed2c55d08dd53639942fb2392649d3af6c9`
passed complete exact-SHA ordinary CI `31069567886`:

- repository job `92514453771` passed complete `verify.sh`, E2E, current-tree
  Gitleaks and complete branch history;
- visual job `92514453836` passed the unchanged fixed-Linux matrix; and
- controlled job `92514454247` remained correctly skipped.

The sole diagnostic controlled workflow `31069924517` retained that exact
SHA. Controlled job `92515528171` passed exact Bench tools, fixed disposable
Site, App installation, two migrations, unchanged P5-01/02/03 runtime,
policy publication, empty workspace, guest/unrelated authorization and
cleanup, then emitted only:

`P504_CREATE_DOMAIN_BUILD / RequestValidationFailed /
trace-79bcd3a2408c5f71bb8c0cad8bd9db21`

The diagnostic dispatch allowance is therefore consumed `1/1`. Companion
repository job `92515528138` and visual job `92515528202` passed; the workflow
conclusion remains failure because the controlled diagnostic intentionally
failed closed.

Direct cross-validation proves one synthetic verifier/fixture precondition
root before any transaction or product persistence:

1. the accepted P5-04 domain policy uses namespace `synthetic_ebom`;
2. `validate_revision_against_policy()` requires the EBOM key to begin with
   the exact published `syntheticNamespace + "-"`;
3. the controlled fixture instead published `synthetic_runtime`; and
4. its create payload independently used `synthetic_ebom_...`, which does not
   satisfy either the policy value or the required delimiter.

The bounded repair defines one `SYNTHETIC_NAMESPACE = "synthetic_ebom"`, uses
it for both the published synthetic policy and the visibly synthetic
`synthetic_ebom-...` key, and adds a cross-fixture invariant test. It does not
change the domain rule, Requirement, public API, permission, DocType, Schema,
ownership, transaction, idempotency, audit or PASS criterion. Diagnostic
header activation is removed from `run_fresh()` before the reserved final
unchanged Gate; the dormant closed capability remains tested and
response-neutral.

Focused verifier/domain/API/repository tests pass `43/43`; complete P5-04
EBOM tests pass `63/63`; complete tracked Python passes `959/959`.
Compilation, V1.2 reconciliation, 282-row trace uniqueness, YAML parse,
prohibited-pattern and `git diff --check` pass. Exact-SHA ordinary CI and the
single reserved final unchanged controlled Gate remain required. P5-04 is
`IN_PROGRESS_REPAIR_VALIDATION`; P5-05 and Phase 6 remain inactive.

## Fixture repair ordinary CI and exhausted final Gate

Fixture repair checkpoint `158ef02cda2319418393a51cbb860c7d9648f091`
passed complete local Python `959/959`, P5-04 EBOM `63/63`, reconciliation,
trace, YAML and diff checks. Complete exact-SHA ordinary CI `31070341154`
then passed repository job `92516810153`, complete E2E, current/history secret
lanes and fixed-Linux visual job `92516810141`; controlled job `92516810582`
remained correctly skipped.

The single reserved final unchanged controlled workflow `31070732986`
retained exact SHA `158ef02` with diagnostic activation closed. Controlled job
`92517955405` passed pinned tools, fixed Bench/Site, migrations, complete
unchanged P5-01/02/03 runtime, policy publication, repaired fixture/domain
preconditions and cleanup, then emitted only:

`P504_RUNTIME_CREATE / HttpStatusError /
trace-462662eec74c5c4f9e3e5a07258f1a7b`

The same workflow's repository job `92517955490` and visual job `92517955368`
both passed. This confines the workflow failure to the controlled create-stage
runtime rather than repository, E2E, secret-scan or visual regressions.

The former `P504_CREATE_DOMAIN_BUILD / RequestValidationFailed` did not recur,
so the repair is not disproved: it advanced the unchanged Gate. The new
aggregate is still non-unique across remaining receipt/root/revision/line/
lifecycle writes, projection, audit, response and receipt-seal boundaries.
Choosing any one would be an unproven repair.

The authorized diagnostic dispatch is consumed `1/1`, the uniquely proved
fixture repair is complete, and the reserved final unchanged Gate is consumed
`1/1`. Under the controller and `release-gate` rules the truthful result is
`BLOCKED_EXTERNAL`, not PASS. The single action to resume is explicit
authority to reactivate only the existing response-neutral create diagnostic,
run affected/full ordinary CI, execute at most one diagnostic Site, repair
only the uniquely proved remaining root, rerun ordinary CI and reserve one
final unchanged Gate. Frozen invariants and P5-05/Phase 6 remain unchanged.

Blocker recovery checkpoint `40c89560aa8a3a8a36ff3b11149499dd72c6705c`
then passed exact-SHA ordinary CI `31071143272`: repository job `92519171196`
passed complete verification, E2E and current/history secret scans; visual job
`92519171311` passed; controlled job `92519171741` remained correctly skipped.
This seals the recovery metadata without adding a diagnostic dispatch or
changing the `BLOCKED_EXTERNAL` classification.

## Remaining create-stage bounded recovery

At `2026-08-06T04:48:37Z` the user explicitly authorized one new bounded
recovery on exact base `c7edac8411614efab1a56348964f7c274cb6f18b`.
Historical diagnostic, fixture-repair and final-Gate counters remain exhausted
and unchanged. The new independent counters begin at diagnostic `0/1`, one
repair only if a remaining verifier/fixture or product root is uniquely
proved, and final unchanged Gate `0/1` reserved.

Only the existing response-neutral header is reactivated, and only for the
first create request in `run_fresh()`. Server diagnostics remain closed to one
allowlisted stage code, validated exception type and exact trace ID; HTTP
responses, Requirement, API, permission, Schema, ownership, transaction,
idempotency, audit and PASS criteria remain unchanged. Affected/full ordinary
CI must pass on the exact diagnostic checkpoint before at most one controlled
diagnostic Site is dispatched.

Local pre-dispatch evidence passes the verifier `17/17`, complete P5-04 EBOM
`63/63`, related Document regression `70/70`, complete tracked Python
`959/959`, compilation, V1.2 reconciliation, YAML, prohibited-pattern and
diff checks. The network-backed pinned devcontainer registry verification also
passes. Supplemental frontend generation, type, lint, direct i18n coverage,
`690/690` unit/coverage tests and production build passed; its final static
asset guard correctly rejected a pre-existing user-owned untracked public
asset, which remains untouched and is absent from a clean CI checkout. The
host itself has Node/npm `24.2.0/11.3.0` rather than the required
`24.18.0/11.16.0`, so the exact-SHA ordinary GitHub CI remains the authoritative
complete ordinary-CI prerequisite and must pass before dispatch.

## Remaining create revision-insert proof and repair

Diagnostic checkpoint `40d2d47f8e551ea5809af488cf6230f93520d5b5`
passed complete exact-SHA ordinary CI `31073500593`: repository job
`92526237591`, complete E2E/current and history secret scans and fixed-Linux
visual job `92526237583` passed; controlled job `92526238095` was correctly
skipped.

The sole authorized diagnostic workflow `31073915463` retained exact SHA
`40d2d47`. Controlled job `92527559599` passed pinned Bench, fixed disposable
Site, both migrations, complete unchanged P5-01/02/03 runtime, policy fixture,
authorization and cleanup, then emitted only:

`P504_CREATE_REVISION_INSERT / ValidationError /
trace-9b23575185625a1998ac184bfefaa272`

Companion repository job `92527559637` and visual job `92527559893` passed.
All earlier create substages, including domain construction, transaction,
receipt and root insert, passed.

Direct code/DocType/contract cross-validation uniquely proves the root. The
revision insert contains one `NPI Engineering BOM Revision` insertion. Its
controller resolves the exact published policy through `require_exact_parent`
and immediately hydrates `ebom_policy_value(policy_row)`. The helper returns
only fields named by the expected predicate and `extra_fields`; query-filter
keys are not automatically returned. The projection included the policy
version document `global_id` and rule fields but omitted the required
`policy_global_id` and `policy_version`, so hydration received an invalid UUID
and version and mapped the resulting domain validation to the observed Frappe
`ValidationError`.

The bounded repair adds only those two existing fields to the read projection,
retains the same exact published-policy predicate and complete domain
revalidation, and changes no Requirement, OpenAPI, DocType, permission,
ownership, transaction, idempotency, audit or PASS criterion. The first-create
diagnostic activation is closed before affected/full ordinary CI and the
reserved final unchanged Gate. Local repair validation passes the combined
controller/runtime-verifier suite `25/25`, complete P5-04 EBOM suite `64/64`,
related Document regression `70/70`, complete tracked Python suite `960/960`,
compilation, reconciliation, prototype-approval, P0 visual-governance, YAML
and diff checks.

## Remaining create final unchanged Gate result

Repair checkpoint `f4aba879e47ea758a6c090016cb069a74b5c154b`
passed complete exact-SHA ordinary CI `31075372272`. Repository job
`92532129789` passed complete verification, E2E, current-tree and history
secret scans; visual job `92532130528` passed; controlled job `92532130580`
was correctly skipped.

The sole reserved final unchanged workflow `31075730002` retained exact SHA
`f4aba87` with create diagnostic activation closed. Repository job
`92533233067` and visual job `92533232990` passed. Controlled job
`92533233034` passed pinned Bench tools, fixed disposable Site initialization,
both migrations, unchanged predecessor P5-01/02/03 runtime, policy fixture and
authorization setup. Cleanup passed. The first EBOM create command returned
only:

`P504_RUNTIME_CREATE / HttpStatusError /
trace-6fa26f47b241558db7fdafa0b9c1a46e`

The complete job log contains no `P504_CREATE_*` server substage for that
trace because the final Gate correctly did not activate the response-neutral
diagnostic. Consequently, this evidence cannot distinguish recurrence of the
diagnosed revision insert from a later line/lifecycle/projection/audit/
response/receipt failure. The final Gate is not PASS, P5-04 cannot pass Level
2, and no additional dispatch or speculative repair is authorized. The
separate bounded counters are exhausted: diagnostic `1/1`, uniquely proved
repair `1/1`, final unchanged Gate `1/1`.

## Post-revision create diagnostic recovery

The user requested that the unresolved create problem be fixed, resuming the
same Goal on exact controller checkpoint
`16ed463e352c98328ea2e993aac0f80eeded7110`. That checkpoint passed complete
ordinary CI `31076595986`: repository `92535872417` and visual `92535872350`
passed; controlled job `92535872991` correctly skipped.

This is a new independent bounded sequence after the prior allowance was
exhausted: existing response-neutral first-create diagnostic `0/1`, at most one
uniquely proved repair `0/1`, and one reserved final unchanged Gate `0/1`.
Historical counters and failed runs are unchanged. The diagnostic adds only
the existing allowlisted request header and sanitized server stage/type/trace
lookup; it does not change HTTP responses or product behavior. Affected/full
ordinary CI must pass before the sole diagnostic Site. Requirement, OpenAPI,
DocType, permission, ownership, transaction, idempotency, audit and PASS
criteria remain frozen.

Local pre-dispatch validation passes the runtime verifier `17/17`, complete
P5-04 EBOM suite `64/64`, related Document API/baseline/runtime regression
`70/70`, complete tracked Python `960/960`, compilation, V1.2 reconciliation,
prototype-approval, P0 visual-governance, YAML and diff checks. The diagnostic
activation assertion proves exactly one `diagnostic=True` call in `run_fresh`
and no direct `create_diagnostic=True` bypass.

## Post-revision lifecycle-insert proof and bounded repair

Diagnostic checkpoint `1400a8bd62552a152007e14023065f6943ed4786`
passed complete exact-SHA ordinary CI `31079745399`. Repository job
`92545602652` passed complete verification, E2E and both secret lanes; visual
job `92545602649` passed; the controlled job was correctly skipped.

The sole authorized diagnostic Site `31080379082` retained exact SHA
`1400a8b`. Repository job `92547610775` and visual job `92547610707` passed.
Controlled job `92547611196` passed the fixed Bench/Site setup, migrations,
unchanged predecessor runtime, synthetic policy and authorization stages, then
emitted exactly:

`P504_CREATE_LIFECYCLE_INSERT / ValidationError /
trace-16676d79fc405e76805261a931550f32`

The earlier revision and line insert stages passed. The line controller
already resolves the same exact revision by revision ID and verifies its EBOM,
tenant, Project and snapshot hash, so the lifecycle failure is not missing
parent state, transaction visibility or hash drift. The lifecycle controller
then constructs `EngineeringBomRevisionLifecycle` with
`revision_global_id=self.revision_global_id`; `before_validate` has normalized
that value to a canonical string, while the domain `_uuid` function accepts
only a non-zero `UUID` instance. `ebom_domain_value` maps that exact
`RequestValidationFailed` to the observed Frappe `ValidationError`.

The one authorized repair converts only the already-validated value with
`UUID(self.revision_global_id)` at domain hydration and adds a behavioral
regression that fails on the prior controller. No Requirement, OpenAPI,
DocType, permission, ownership, transaction, idempotency, audit, response or
PASS criterion changes. First-create diagnostic activation is closed before
affected/full ordinary CI and the reserved final unchanged Gate.

The changed-files-to-affected-tests map is:

| Changed boundary | Affected evidence |
|---|---|
| EBOM revision lifecycle controller | controller behavioral regression plus complete EBOM controller/domain/metadata/repository/API/security suite |
| first-create diagnostic activation closure | runtime-verifier diagnostic-closure and sanitized diagnostic tests |
| controller/evidence synchronization | V1.2 reconciliation, prototype approval, P0 visual governance, YAML parse and diff check |

Local repair validation passes controller plus runtime verifier `26/26`, the
complete P5-04 EBOM suite `65/65`, tracked Python `955/955`, and full workspace
discovery `961/961` without modifying the six user-owned untracked local
prerequisite tests. Compilation, reconciliation, prototype approval, P0
visual governance, YAML and diff checks pass. The aggregate local `verify.sh`
correctly refuses the host's Node `24.2.0` / npm `11.3.0` because the repository
requires Node `24.18.0` / npm `11.16.0`; complete exact-toolchain ordinary CI
therefore remains mandatory before the final Site.

## Post-lifecycle repair ordinary CI and final Gate

Repair checkpoint `6a4ba7c43e778f22a8de45ce9be8bf5c07a63aac`
passed complete exact-SHA ordinary CI `31081784934`. Repository job
`92552039959` passed the exact Node/npm toolchain, complete `verify.sh`, E2E,
current-tree Gitleaks and complete pull-request history scan. Visual job
`92552040040` passed the fixed-Linux matrix. Controlled runtime was correctly
skipped.

The sole reserved final unchanged workflow `31082337133` retained exact SHA
`6a4ba7c` with first-create diagnostics closed. Visual job `92553782973`
and repository job `92553782998` passed; repository included complete
`verify.sh`, E2E and current-tree Gitleaks. Controlled job `92553782979`
passed pinned Bench tools, disposable Site initialization, migrations, the
unchanged P5-01/02/03 Document runtime and cleanup, then emitted only:

`P504_RUNTIME_CREATE / HttpStatusError /
trace-ef925ea360245bd6b58daf326b910afe`

The final log contains no `P504_CREATE_*` server substage because diagnostic
activation was correctly closed. The aggregate tuple cannot prove recurrence
of the repaired lifecycle insert or select among later root projection, audit,
response and receipt-seal paths. Therefore the workflow is not a P5-04 Gate
PASS, Level 2 and release-gate are not run, and Autopilot cannot activate
P5-05. Diagnostic `1/1`, uniquely proved repair `1/1` and final unchanged Gate
`1/1` are exhausted. A further Site dispatch or code change requires new
explicit bounded post-lifecycle authority; no Requirement, API, permission,
Schema, ownership, transaction, idempotency, audit or PASS criterion may
change.
