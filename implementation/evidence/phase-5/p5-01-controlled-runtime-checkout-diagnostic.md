# P5-01 Controlled Runtime Checkout Diagnostic Round

Recorded: `2026-07-31T02:08:45Z`

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

`COMPLETE DIAGNOSTIC CHECKPOINT / INSUFFICIENT STAGE ATTRIBUTION`

P5-01 is not `PASS`, none of its seven requirements is promoted, and P5-02
remains inactive.

## Authority and exact sequence

The user explicitly authorized one additional bounded P5-01
controlled-runtime repair round after the checkout diagnostic limit was
exhausted. The authority permits only:

1. extending sanitized diagnostics to the document-workspace boundary;
2. one diagnostic-only controlled-Site dispatch;
3. fixing only the checkout transaction root proven by that dispatch;
4. affected tests and complete normal CI; and
5. one final unchanged controlled-Site Gate.

No Requirement, API, permission, architecture, data ownership, DocType,
Schema, transaction, lock, audit, idempotency or PASS criterion may be
changed to obtain a result.

## Proven diagnostic gap

Controlled run `30573778175` already passed exact setup, both migrations,
schema checks, Project and policy creation/publication, controlled document
creation and its immediate replay. Checkout then returned HTTP `500`.

The BFF already writes a safe structured diagnostic containing only:

- `code=UNEXPECTED_BFF_EXCEPTION`;
- a bounded exception type; and
- the incoming deterministic trace ID.

The runtime verifier discarded its deterministic trace identity and the
generic document-workspace assertion did not use the common sanitized failure
boundary. Mandatory cleanup then removed the ephemeral runtime before the
four checkout transaction candidates could be distinguished.

## Diagnostic-only implementation

| Boundary | Diagnostic change | Safety invariant |
|---|---|---|
| Request identity | Preserve exact generated request and trace IDs in the verifier result | No header, cookie or credential is emitted |
| Document workspace | Reuse `require_http_status` for every document-workspace result | No product response or Gate rule changes |
| Safe BFF record | Match exact `code / exceptionType / traceId` schema and exact incoming trace | Arbitrary log text and extra keys are rejected |
| Log boundary | Accept only two fixed physical `npi_core.log` paths below the fixed Bench | Symlink and resolved-path escape are rejected |
| Read bound | Read only the final 64 KiB and scan newest matching lines first | No full log, traceback or request dump is retained |
| Output bound | Emit only validated `exc_type` and fixed `diagnostic_code` | Raw exception messages, traceback, payload, cookies and credentials are excluded |

No product application, repository, controller, DocType, migration, contract,
permission, transaction or UI file is changed in this checkpoint.

## Changed files → affected checks

| Changed files | Affected checks |
|---|---|
| `scripts/verify_document_runtime.py` | verifier import/compile, exact diagnostic identity, safe-log parsing, document-workspace failure boundary, unchanged controlled runtime command |
| `tests/test_phase5_document_runtime_verifier.py` | response sanitization, trace matching, invalid type/unrelated trace rejection, credential non-disclosure, deterministic identity |
| controller/evidence files | YAML structure, Reconciliation freshness, Task status and whitespace |

## Local evidence

- focused document-runtime verifier: `15/15 PASS`;
- complete tracked Python suite: `781/781 PASS`;
- changed Python compilation: `PASS`;
- changed-file whitespace: `PASS`.

The host Node/npm versions are not the repository pins, so complete normal CI
remains the canonical repository/frontend/visual/security environment. No
dependency was installed and no local product runtime result is claimed.

## Terminal evidence

Exact checkpoint:
`e4b284f6360a852ffd81d6a9e7b0f41f65f363a9`.

Normal CI `#101`, run `30598406263`, passed:

- repository job `91055706505`;
- fixed-Linux visual job `91055706451`;
- complete repository verification and `285/285` non-visual browser cases;
- current-tree and complete pull-request-history secret scans.

The sole authorized diagnostic workflow was `#102`, run `30598733723`, on
the same exact SHA:

- controlled runtime job `91056666308`: diagnostic `FAIL`;
- repository job `91056666373`: `PASS`;
- visual job `91056666259`: `PASS`;
- exact tools, fixed Site/database guards, both app installations and both
  migrations: `PASS`;
- checkout diagnostic:
  `exc_type=ValidationError; diagnostic_code=UNEXPECTED_BFF_EXCEPTION`;
- bounded cleanup: `PASS`.

The diagnostic is not a Gate PASS. It proves the safe trace chain works, but
the existing BFF record contains no checkout transaction-stage code.
`ValidationError` remains shared by command-receipt, lock-event, exact
projection and response-receipt seal validations. A product repair would
therefore still be a guess. The resulting Hard Blocker is recorded in
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-stage-blocker.md`.
