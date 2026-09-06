# P5-01 Controlled Runtime Checkout Stage Diagnostic Hard Blocker

Recorded: `2026-07-31T02:37:04Z`

Task:
`P5-01 — Document and design revision`

Requirements:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

Result:

`BLOCKED_EXTERNAL — AUTHORIZED DIAGNOSTIC DISPATCH EXHAUSTED WITHOUT A
UNIQUE CHECKOUT TRANSACTION STAGE`

P5-01 is not `PASS`, none of its seven requirements is promoted, and P5-02
remains inactive. The previously authorized final unchanged controlled-Site
Gate is not consumed.

## Exact checkpoint and reusable PASS evidence

Diagnostic checkpoint:
`e4b284f6360a852ffd81d6a9e7b0f41f65f363a9`.

Normal CI `#101`, run `30598406263`, passed on that exact SHA:

- repository job `91055706505`;
- fixed-Linux visual job `91055706451`;
- complete repository verification;
- `285/285` non-visual browser cases;
- current-tree and complete pull-request-history secret scans.

Local focused verifier `15/15`, complete tracked Python `781/781`, compile,
Reconciliation, YAML and whitespace checks remain reusable.

## Sole authorized diagnostic result

Workflow dispatch `#102`, run `30598733723`, matched the exact diagnostic
SHA.

- controlled runtime job `91056666308`: diagnostic `FAIL`;
- repository job `91056666373`: `PASS`;
- visual job `91056666259`: `PASS`;
- exact Bench/uv/Yarn setup: `PASS`;
- fixed disposable Site/database guard: `PASS`;
- both NPI app installations and both migrations: `PASS`;
- cleanup of ephemeral containers, volumes and network: `PASS`.

The checkout boundary emitted only:

`exc_type=ValidationError; diagnostic_code=UNEXPECTED_BFF_EXCEPTION`

No raw exception message, traceback, request body, cookie or credential was
emitted.

## Why this is not yet a proven repair root

The new evidence excludes an arbitrary status-only HTTP failure and normal
Python response-reconstruction errors. It does not uniquely identify a
checkout transaction stage because the same Frappe `ValidationError` class can
still originate from:

1. the actor/project/document-bound idempotency receipt;
2. immutable lock-event exact parent, type, version or snapshot validation;
3. the controlled-document exact lock-event projection; or
4. the final idempotency response seal.

The audit boundary would use `PermissionError` for its explicit write guard,
and ordinary response conversion failures use normal Python exception types,
so those candidates are less consistent with the observed class. That
inference does not prove which of the four remaining validation sites failed.

The safe BFF record intentionally contains only `code`, `exceptionType` and
`traceId`; it contains no transaction-stage code. Mandatory cleanup correctly
destroyed the disposable Site, so no retained database or raw server log may
be used after the run.

Changing timestamp normalization, lock-event order, projection exactness,
idempotency validation or receipt sealing now would be a speculative repair.
It could also weaken immutable history, transaction atomicity or replay truth.
That is prohibited by the explicit “fix only the proven checkout transaction
root cause” authorization.

## Safe bounded solution

One additional diagnostic checkpoint must:

1. define a closed allowlist of checkout stage codes for receipt insert,
   lock-event insert, projection save, audit append, response build and
   receipt seal;
2. record only the matching stage code, validated exception type and exact
   trace ID through the existing safe diagnostic writer;
3. add direct tests proving no raw message, traceback, payload, cookie or
   credential can enter output;
4. pass affected checks and complete normal CI;
5. execute exactly one stage-diagnostic controlled-Site dispatch; and
6. repair only the stage proven by that result.

The final unchanged
`bash scripts/verify-frappe-runtime.sh --document-only` Gate already
authorized by the user remains reserved for after the proven repair.

No Requirement, API, permission, architecture, data ownership, Schema,
transaction, lock, audit, idempotency or PASS criterion may be weakened.

## Single unblock action

`Explicitly authorize one additional bounded P5-01 checkout stage-diagnostic
checkpoint and one controlled-Site diagnostic dispatch, limited to allowlisted
stage code + validated exception type + exact trace ID, followed by repair of
only the proven stage; retain the already authorized final unchanged
controlled-Site Gate.`
