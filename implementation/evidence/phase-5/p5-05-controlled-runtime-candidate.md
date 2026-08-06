# P5-05 Controlled Runtime Candidate

Recorded: `2026-08-06T13:26:20Z`

Status:
`READY FOR COMPLETE ORDINARY CI — CONTROLLED SITE NOT YET DISPATCHED`

Requirement: `FR-DS-013`

Starting checkpoint:
`cbb0642324d61529d1ee8906dc2d0d42e6e611ca`

Starting checkpoint CI:
`31105198326` (`PASS`; repository `92628403615`, visual `92628403529`)

## Candidate boundary

- Extends the existing fixed disposable-Site `--document-only` lane only
  after the retained P5-04 released EBOM and its cross-process replay pass.
- Provisions one visibly synthetic, exact Project-scoped, published Mock
  requester policy through the existing guarded `publish_policy_write()`
  administration context. The fixed internal actor is the only requester.
- Proves the seven P5-05 DocTypes are synchronized after the lane's two
  migrations, then proves guest denial, empty list/policy truth, exact released
  input, create, list/detail, exact replay, changed-payload conflict, immutable
  request/node/mapping/result/audit cardinality and cross-process replay.
- Proves every Mock node remains `validated` at attempt zero, with no formal
  Item/MBOM/target version, no dispatch/retry/reconcile capability and no
  Outbox message.
- Adds an independent literal-true `npi_p5_05_routes_disabled` cycle. The
  disabled P5-05 path returns the closed service-unavailable problem while the
  exact P5-04 EBOM remains readable; recovery restores the persisted request.
- Restores the P5-05 switch to absent in the fail-safe cleanup path and retains
  the existing final Docker volume cleanup. The controlled artifact now states
  the cumulative truthful scope `p5-01-through-p5-05`.

No product Requirement, API, role, DocPerm, Schema, ownership, transaction,
idempotency, audit, translation, visual or PASS rule changed. No production or
sandbox endpoint, credential, service identity, network adapter, worker,
Outbox dispatch, ERPNext object or formal identifier is introduced.

## Changed-files -> affected tests

| Changed boundary | Verification | Result |
|---|---|---|
| P5-05 verifier and fixtures | new verifier contract plus P5 publish modules | affected group `60/60` PASS |
| cumulative P5 runtime shell/workflow | shell syntax, retained P5-04 verifier contract and new ordering/scope tests | PASS |
| complete tracked Python regression | `python3 -m unittest discover -s tests` | `1006/1006` PASS |
| compilation | `python3 -m compileall -q apps/npi_core apps/npi_integration scripts tests` | PASS |
| governance | prototype approval, P0 visual inventory and V1.2 reconciliation | PASS |
| prohibited-pattern and whitespace scans | repository `rg` boundary and `git diff --check` | PASS |

The local machine has Node `v24.2.0`/npm `11.3.0`, not the pinned repository
Node `v24.18.0`/npm `11.16.0`, and has no fixed disposable Bench/Site. The
aggregate local verifier therefore correctly stopped at its toolchain guard;
it was not bypassed. Complete ordinary CI on the exact candidate SHA must pass
the pinned toolchain and complete repository/browser/visual/secret lanes
before any controlled Site dispatch.

The pre-existing user-owned untracked frontend asset and unrelated local
evidence/development files were not modified or staged.

## Security and failure evidence

- Bench fixtures strip runtime passwords and database variables from their
  subprocess environment and return only closed JSON evidence.
- A failed HTTP stage emits only an allowlisted `P505_RUNTIME_*` code, a
  validated exception type and exact synthetic trace ID; response messages,
  traceback, paths and secrets are discarded.
- The verifier talks only to the validated loopback disposable Site. It does
  not contain an ERP endpoint or use a generic HTTP client library.
- A Bench fixture failure remains fail closed as `BenchFixtureError`; it cannot
  be relabelled `PASS`. Under the user's standing recovery authority, an opaque
  controlled failure opens one serial response-neutral diagnostic cycle only
  after complete ordinary CI.

## Rollback and next action

Before dispatch, revert only this verifier/workflow candidate. After a
controlled run, retain its immutable artifact and run history; any repair is a
reviewed forward fix. Never delete publish-request history, weaken the Gate or
contact ERPNext as rollback.

The next action is complete exact-SHA ordinary CI. Only after repository,
complete E2E, both secret lanes and the complete fixed-Linux visual matrix pass
may Autopilot dispatch one unchanged controlled P5 Site Gate. A Gate PASS then
permits the P5-05 Level 2 and Phase 5 Level 3 release-gate review.
