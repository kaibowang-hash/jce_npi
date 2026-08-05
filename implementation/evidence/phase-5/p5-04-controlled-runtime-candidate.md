# P5-04 Controlled-Site Runtime Candidate

Recorded: `2026-08-05T13:21:38Z`

Status:
`PASS — LOCAL LEVEL 1 CONTROLLED-RUNTIME HARNESS; EXACT-SHA NORMAL CI NEXT`

Task:
`P5-04 — EBOM revision and comparison`

Requirements:

- `FR-DS-011`; and
- `FR-DS-012`.

Starting synchronized checkpoint and remote HEAD:
`0c344fef0dbab4a84dc9ee84e3400a626de8d0c9` (`0 ahead / 0 behind`)

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

Create and push one scoped controlled-runtime candidate checkpoint containing
only the harness, its contract tests, manual-lane declaration and synchronized
P5-04 evidence/controller files. Preserve every user-owned local modification
and untracked asset. Require complete unchanged ordinary CI on the exact SHA;
only then dispatch one controlled Site run. If that run fails, classify the
exact safe stage and repair only a uniquely proven product root within the
controller budget. P5-05 and Phase 6 remain inactive.
