# P5-03 response-contract predicate diagnostic resume

Recorded: `2026-08-03T02:30:57Z`

## Recovery facts

- Existing Codex Goal: `019fb65e-318b-7fb1-8775-0d600b154ef0`; no new Goal
  was created.
- Branch: `codex/npi-v1.2-implementation`.
- Recovery HEAD and remote HEAD:
  `a8a20ec18f5d9d16f28953f3bc100fb8728fb069`.
- Latest complete ordinary CI: `30778815782` (`PASS`, exact recovery HEAD).
- Product repair candidate: `15abf26834027045ccb98e5167a45390e94cb32b`.
- Its complete ordinary CI: `30777828197` (`PASS`).
- Historical final unchanged controlled-Site Gate: `30778190537`
  (`FAIL`, diagnostic activation closed).
- Historical safe tuple:
  `P503_BASELINE_CREATE_RESPONSE_CONTRACT / RuntimeError /
  trace-062ce39fc49457a384bc1acba7afd785`.
- P5-03 status: `IN_PROGRESS_DIAGNOSTIC`; no P5-03 PASS or Level 2 result is
  claimed.

## Authorized boundary

The user authorized one additional behavior-neutral response-contract
predicate ladder in `validate_document_baseline_command` and at most one
diagnostic-only controlled-Site dispatch. The closed ladder covers only:

- project identity and idempotency replay header;
- baseline shape, version, creator, global identity and snapshot hash;
- policy identity, version and hash;
- member cardinality, revision identity/hash, lifecycle version and release
  snapshot hash;
- file cardinality and scan state; and
- private-path and URL exclusion.

Diagnostic output is limited to an allowlisted predicate code, a validated
exception type and the exact trace ID. Exception text, traceback, request,
response, Cookie, credentials, business data and storage paths remain
forbidden.

Affected tests and complete ordinary CI must pass before the sole diagnostic
dispatch. A verifier or synthetic-fixture root follows the Autopilot
Controller classification. Only if the diagnostic uniquely proves a product
predicate does one separate response-contract-only P5-03 product-root
exception become usable. This does not change the global five-round rule.

Before any repair, the proven predicate must be cross-validated against
FR-DS-006, the Requirement anchor, OpenAPI, true DocType fields, permissions,
ownership and transaction invariants. Requirement, API, permission, Schema,
ownership, lock, version, audit, idempotency, transaction order and PASS
criteria are frozen.

After a unique repair, affected tests, complete ordinary CI and one final
unchanged controlled-Site Gate are required. The final Gate must run with the
predicate-diagnostic activation path closed. If the sole diagnostic is not
unique or a frozen invariant must change, execution stops at one recorded Hard
Blocker without a guessed repair.

## Repair accounting

`2b067c1cbd0977d843780d386bfc882b80615b33` remains the fifth completed
ordinary product-root repair. The earlier baseline-create-only exception was
consumed by `15abf26834027045ccb98e5167a45390e94cb32b`. The new authority is a
separate response-contract-only exception and has not been consumed. Neither
behavior-neutral diagnostic convergence nor this checkpoint changes the
global five-round rule.

## Workspace protection

Only the controller/evidence files named by this checkpoint may be staged.
Existing tracked and untracked user changes, including `LAST_RUN.md`, local
development files and generated visual/browser evidence, remain excluded.
