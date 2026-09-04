# P5-01 Controlled Runtime Checkout Stage Diagnostic

Recorded: `2026-07-31T03:53:26Z`

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

State:

`BLOCKED_EXTERNAL — FINAL UNCHANGED GATE EXHAUSTED; PROJECTION-SAVE
VALIDATION SUBSTAGE NOT YET PROVEN`

P5-01 is not `PASS`, none of its seven requirements is promoted, and P5-02
remains inactive.

## Authority

The user explicitly authorized:

`Explicitly authorize one additional bounded P5-01 checkout stage-diagnostic
checkpoint and one controlled-Site diagnostic dispatch, limited to allowlisted
stage code + validated exception type + exact trace ID, followed by repair of
only the proven stage; retain the already authorized final unchanged
controlled-Site Gate.`

No Requirement, API, permission, architecture, data ownership, Schema,
transaction order, lock, audit, idempotency or PASS criterion may change to
obtain a result.

## Diagnostic-only implementation

The checkout command now records one of exactly six stage codes if an
unexpected exception crosses that boundary:

1. `DOCUMENT_CHECKOUT_RECEIPT_INSERT`;
2. `DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT`;
3. `DOCUMENT_CHECKOUT_PROJECTION_SAVE`;
4. `DOCUMENT_CHECKOUT_AUDIT_APPEND`;
5. `DOCUMENT_CHECKOUT_RESPONSE_BUILD`; or
6. `DOCUMENT_CHECKOUT_RECEIPT_SEAL`.

The persistence order and calls are unchanged. Expected domain `NpiProblem`
outcomes do not create unexpected diagnostics. Diagnostic failure cannot
replace the original exception.

The safe BFF record remains exactly:

- `code`;
- `exceptionType`; and
- `traceId`.

The runtime verifier accepts only the six closed codes or the retained generic
fallback, an exact deterministic trace, a validated exception-type token and
the exact three-field schema. It reads only the final 64 KiB of one of two
fixed physical Bench log paths, rejects symlinks/path escape and prefers the
stage record over the later generic BFF record for the same trace.

When a safe record is present, no server response message is emitted. Raw
exception text, traceback, payload, cookie and credential data are excluded.

## Changed files → affected checks

| Changed boundary | Affected checks |
|---|---|
| `documents/frappe_repository.py` checkout stage wrappers | closed allowlist, expected-domain exclusion, secondary-diagnostic behavior, exact six-stage source placement, P5 document repository/domain/API/controller/metadata/contract tests |
| `scripts/verify_document_runtime.py` safe record selection | exact trace/schema/type/code, stage-over-generic preference, unhashable/unreviewed code rejection, body-message suppression, fixed path/symlink/64-KiB bounds |
| focused tests | sanitized non-disclosure, deterministic request/trace identity, complete stage inventory |
| controller/evidence | Reconciliation freshness, YAML structure and whitespace |

## Local evidence

- focused repository and runtime-verifier tests: `28/28 PASS`;
- complete P5 Document module group: `83/83 PASS`;
- complete tracked Python suite: `784/784 PASS`;
- changed Python compilation: `PASS`;
- Reconciliation and YAML: `PASS`;
- whitespace: `PASS`.

The local Python lacks repository Black/flake8 packages, so no local result is
claimed for those commands. Complete normal CI remains the canonical
formatter/lint/repository/frontend/visual/security environment.

## Authorized diagnostic result

- exact diagnostic checkpoint:
  `954bd0d08b9f82614e34cc0e92e67f5de0340db9`;
- complete normal CI `#104`, run `30600587269`: repository, complete E2E,
  fixed-Linux visual and both secret scans `PASS`;
- sole stage-diagnostic dispatch: run `30600943765`, event
  `workflow_dispatch`, exact checkpoint SHA;
- exact tools, fixed disposable Site/database, both apps, both migrations and
  bounded cleanup: `PASS`;
- safe result:
  `ValidationError / DOCUMENT_CHECKOUT_PROJECTION_SAVE`;
- exact request trace: match-validated against the three-field safe record
  before accepting the stage result; the verifier did not echo its value or
  any raw server detail; and
- receipt insert and immutable lock-event insert are therefore proven not to
  be the failing stage. The diagnostic run is not a Gate PASS.

## Rejected repair candidate

The first new lock projection now binds its save to the exact immutable
acquisition-event name returned by the immediately preceding successful
insert. The Controlled Document controller still reads that row from the
database and validates its exact global ID, tenant, Project, Document, lock
ID/version, event type, holder and expiry. An absent command binding retains
the existing exact-filter behavior; a malformed binding fails closed.

The binding exists only around the proven projection `save()`, restores any
prior Frappe flag in `finally`, and changes no DocType, public contract,
permission, event content, lock lease, optimistic version, audit,
idempotency, transaction order or rollback behavior.

Affected local evidence after repair:

- focused repository/controller/verifier: `41/41 PASS`;
- complete P5 Document module group: `85/85 PASS`;
- complete tracked Python suite: `786/786 PASS`;
- changed Python compilation and whitespace: `PASS`.

Exact repair checkpoint
`b2d7ca9256a0dd62a693baa6feea1c53fd33402f` passed complete normal CI run
`30601670711`, including canonical repository formatting/lint/full checks,
complete E2E, fixed-Linux visual and both secret scans.

The retained final unchanged Gate, run `30601980685`, matched that exact SHA.
It passed the fixed tools, disposable Site/database, both apps, both
migrations and bounded cleanup, but checkout again returned the exact safe
result `ValidationError / DOCUMENT_CHECKOUT_PROJECTION_SAVE`.
The same workflow's complete repository/E2E/security job and fixed-Linux
visual job passed; the workflow failed only because the controlled runtime
job correctly rejected checkout.

This disproves the acquisition-event selector hypothesis. The failing stage
is still inside the Controlled Document `save()` lifecycle, after successful
receipt and lock-event insertion, but the allowed evidence does not
distinguish identity/policy hydration, domain reconstruction, optimistic
version validation, exact lock projection validation or a later Frappe save
hook. The failed candidate is forward-reverted in the blocker checkpoint so
no unproved behavior remains.

The exact pushed blocker checkpoint is
`cefe7638b5ab31e424fae6cf691e808c47da68c5`; local and remote SHA match at
`0 ahead / 0 behind`. Its complete normal CI `30602410036` passed the
repository/E2E/security and fixed-Linux visual jobs. The manual controlled
runtime job was correctly skipped for this ordinary PR event, so no additional
dispatch was consumed.

## Hard Blocker and resolution

The one stage-diagnostic dispatch and the retained final unchanged Gate are
both exhausted. Another code repair or controlled-Site dispatch would exceed
the explicit bounded authority. P5-01 remains incomplete and P5-02 remains
inactive.

The smallest safe resolution is one new explicit authorization for:

1. one diagnostic-only checkpoint with a closed allowlist of projection
   validation substages;
2. affected tests and complete normal CI;
3. one controlled-Site diagnostic dispatch;
4. repair of only the uniquely proven substage;
5. affected tests and complete normal CI; and
6. one final unchanged controlled-Site Gate.

No raw exception message, traceback, request, cookie or credential may be
added, and no Requirement, contract, permission, lock, version, audit,
idempotency, transaction order or PASS criterion may be weakened.
