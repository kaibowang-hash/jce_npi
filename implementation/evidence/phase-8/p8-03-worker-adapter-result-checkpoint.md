# P8-03 Checkpoint 3 — Durable Item Worker, Adapter and Result Truth

Recorded: `2026-08-16T16:07:13Z`

Decision: `PASS — CHECKPOINT 3; CHECKPOINT 4 AUTHORIZED`

Exact product checkpoint:
`1a2c5bebdf5288d6c6570c87eb2753908867bea8`

Final ordinary pull-request CI:
`31956908978` (`PASS`)

## 1. Bounded outcome

Checkpoint 3 completes only the frozen P8-03 worker, transport and observed-
result slice:

- an operation-specific bounded worker claims only pending version-1 Item
  Outbox messages or processing messages whose lease expired; live claims are
  refused, every recovery has a fresh token and scheduler recovery remains
  bounded;
- the worker commits the claim before target preparation, reloads and locks the
  exact request/Outbox/profile/source/current-mapping state, rejects drift and
  writes the immutable attempt before crossing the adapter boundary;
- an attempt freezes exact target idempotency, request/source/profile hashes,
  expected target and mapping versions, operation, trace, actor and timeout
  policy. Recovery before the boundary may continue that same attempt, while
  recovery after the boundary never redispatches it;
- the closed adapter registry is disabled by default. Mock is a no-op;
  disposable synthetic execution is network-free and non-authoritative; and a
  Sandbox adapter is available only through an explicitly injected,
  non-production, operation-bound profile and credential resolver;
- response/fault classification distinguishes synthetic, authenticated
  authoritative Sandbox, malformed/mismatched 2xx, authentication/binding,
  business validation, rate limit, 5xx, timeout and other uncertain outcomes.
  HTTP acceptance, a crossed-boundary exception or an ambiguous result commit
  never becomes formal success;
- terminal request/result/Outbox/audit persistence is atomic. Only an
  authenticated authoritative Sandbox result with exact source/profile/result
  binding may create a mapping observation and advance the mapping head under
  compare-and-set; synthetic execution has no formal code/version or mapping;
  and
- the cumulative disposable-Site fixture/verifier now covers default-disable,
  explicit network-free synthetic request/Outbox/claim/attempt/result,
  restart replay and adapter-call counting. The final Level 3 Gate remains the
  authoritative disposable-Site execution and migration proof.

No UI, generic retry/replay/reconciliation, default profile, networked
Sandbox, production endpoint/credential/contact, MBOM behavior or formal Item
mapping was activated.

## 2. Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `item_publish/worker.py` | claim-before-work commit, same-attempt recovery, boundary marking, no post-boundary redispatch, classified result and bounded scheduler tests |
| `item_publish/worker_repository.py` | exact request/Outbox/source/profile/mapping locks, immutable attempt, target idempotency, atomic terminal result/audit, authoritative observation/head compare-and-set and rollback tests |
| `item_publish/adapters.py` | closed registry, disabled/Mock/synthetic/Sandbox modes, non-production host/redirect/operation/credential/timeout controls, response/fault classification and redaction tests |
| hook, runtime fixture/verifier and CI wiring | default-disabled installation, marker-gated network-free synthetic runtime, restart replay, adapter-call count, retained cumulative scope and no production traffic assertions |
| focused P8-03 tests | pending/live/expired leases, crash/commit ambiguity, rate/5xx/business/malformed/timeout outcomes, stale mapping, synthetic no formal mapping and no generic operations |

The product range
`a5581a9ba19281673437889e378531d4a8cd256b..1a2c5bebdf5288d6c6570c87eb2753908867bea8`
contains `15` files, `4,008` insertions and `13` deletions. Controller and
evidence files were not part of that product commit.

## 3. Local Level 1 and Task Gate evidence

- Complete affected P8-03 Item suite: `73/73 PASS`.
- Full local repository Task Gate: `2,100/2,100 PASS`; six pre-existing
  untracked local-prerequisite tests explain the difference from the clean CI
  count. Development-container, prototype approval, P0 visual-governance and
  V1.2 reconciliation checks pass.
- Runtime-verifier unit tests, Python compilation, shell syntax, current-task
  verification, prohibited production/network scans, staged and exact-commit
  Gitleaks and `git diff --check`: PASS.
- Task Diff Review confirms no UI or translation source changed, no route
  broadening, caller-selected target authority, default profile, production
  host/credential, formal mapping from Mock/synthetic, generic retry/replay/
  reconcile API, MBOM command or production contact.

## 4. Exact-SHA ordinary CI evidence

Pull-request run `31956908978` completed successfully at exact head
`1a2c5bebdf5288d6c6570c87eb2753908867bea8`:

- repository `95188821489`: `2,094/2,094` tracked Python tests plus repository,
  prototype, P0 visual-governance and V1.2 reconciliation verification;
- frontend `95188821475`: `60/60` files, `933/933` unit tests, `426/426` E2E,
  `7,879` literal English sources with `100%` direct `zh`/`zh-TW` coverage,
  coverage thresholds, production build and zero vulnerabilities;
- secret `95188821470`: `26` first-parent task commits and `532` complete
  branch commits contain no leak. Artifact `9266184668` has digest
  `sha256:ea0c476ad0e0a2a9de807db0eee93a0f43ef87fb03e020e868600ae62ecd2472`;
  and
- visual `95188821520`: unchanged fixed-Linux matrix `119/119 PASS`. Artifact
  `9266236939` has digest
  `sha256:54e912556e0f07982df28a875d90a3f05bfbf18782a3d438009a293d6bc2ba07`.

Controlled preflight `95190357476` and cumulative runtime `95190358036`
correctly skip because this is ordinary checkpoint CI, not the final Level 3
dispatch. The runtime fixture and verifier are installed for the cumulative
exact-SHA Gate; ordinary CI neither contacts nor writes any target.

## 5. Security, rollback and transition

The reviewed boundary resolves authority from committed server-owned state,
retains exact target idempotency, prevents live-lease theft and forbids
redispatch once an attempt may have reached the target. Diagnostics and audits
retain structural hashes and allowlisted classifications, not credentials,
payload bodies or raw target errors. The only executable checkpoint fixture is
explicitly marked, disposable, network-free and non-authoritative.

Before the adapter boundary, rollback disables Item routes, enqueue and worker
and retains request/idempotency/Outbox/audit for reviewed forward repair. After
the boundary, it disables new commands and claims, retains every request,
event, lease, attempt, response hash, result, uncertainty, observation,
mapping head and audit, and never deletes, blindly redispatches, rewrites to
success, changes an Item Code, mutates released source or compensates a target.

This evidence closes checkpoint 3 only. Standing continuous-delivery authority
activates checkpoint 4: the bounded dense trilingual EBOM Item execution
workspace, truthful status/disabled-state presentation and one guarded primary
request action. Retry/reconcile controls, production ERPNext/JCE, MBOM and
P8-04 through P8-09 remain inactive. P8-03 completes only after checkpoint 4
exact-SHA ordinary CI and the final Level 3 Gate pass.
