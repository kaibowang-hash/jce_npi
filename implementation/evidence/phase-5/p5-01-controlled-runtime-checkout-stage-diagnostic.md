# P5-01 Controlled Runtime Checkout Stage Diagnostic

Recorded: `2026-07-31T03:25:04Z`

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

`IN_PROGRESS — PROVEN PROJECTION-SAVE REPAIR LOCALLY PASS; NORMAL CI AND FINAL
UNCHANGED CONTROLLED-SITE GATE PENDING`

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
- Reconciliation and YAML: pending controller update verification;
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

## Proven-stage-only repair

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

## Exact remaining sequence

1. verify controller/Reconciliation/YAML and commit only the proven-stage
   repair;
2. push and pass complete normal CI on its exact SHA; and
3. execute the already authorized final unchanged
   `bash scripts/verify-frappe-runtime.sh --document-only` Gate.

The diagnostic dispatch is not a Gate PASS even if it advances. Only the final
unchanged run may provide the missing P5-01 controlled-runtime Gate evidence.
