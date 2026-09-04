# P5-01 Controlled Runtime Datetime Repair

Recorded: `2026-07-30T18:59:43Z`

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

`COMPLETE REPAIR / FAILED CONTROLLED-SITE GATE — CHECKOUT HTTP 500`

P5-01 is not `PASS`, none of its seven requirements is promoted, and P5-02
remains inactive.

## Authority and boundary

The user explicitly authorized one additional bounded repair beyond the
exhausted owner round. This batch may only:

1. separate canonical API/snapshot UTC text from Frappe database Datetime
   formatting across the affected P5 Document fields;
2. preserve semantic immutable and exact-parent comparisons across Frappe
   datetime objects and storage strings;
3. add bounded diagnostics containing only a validated exception type and a
   controlled server message;
4. run affected checks, normal CI and one unchanged controlled-Site Gate.

It changes no Requirement, API contract, permission, architecture, data
ownership, Schema, timestamp semantic, production policy or PASS criterion.

## Requirement → code → test → evidence

| Boundary | Code | Tests/evidence |
|---|---|---|
| Frappe Datetime persistence | `documents/frappe_validation.py`; eight P5 Document controllers | exact storage adapter, aware/naive/canonical inputs, all thirteen field assignments |
| Immutable and parent truth | shared document validation plus controlled-document lock projection | semantic equality across hydrated datetime and storage text; real change still denied; unchanged active lock survives revision projection |
| Canonical snapshot truth | revision, lock-event and disabled share-grant controllers | stored fields are space-separated while frozen snapshot values remain canonical `Z` |
| Sanitized runtime diagnosis | `scripts/verify_document_runtime.py` | only bounded `exc_type` and controlled message; traceback, exception, request, cookie and credential values excluded |

## Changed files → affected checks

| Changed files | Affected checks |
|---|---|
| document Frappe validation and eight document controllers | all P5 document controller/domain/repository/API/metadata/contract tests; Python compile; prohibited-pattern and diff checks |
| controlled-runtime verifier | P5 runtime-verifier tests; shared runtime safety regressions; unchanged real `--document-only` Gate |
| controller and evidence files | YAML/trace/reconciliation consistency; status and whitespace review |

## Local incremental evidence

- focused new controller/runtime diagnostic tests: `23/23 PASS`;
- complete P5 document module group: `77/77 PASS`;
- complete tracked Python suite: `778/778 PASS`;
- affected Python compilation: `PASS`;
- Reconciliation, YAML structure, prohibited-pattern and `git diff --check`:
  `PASS`.

The host does not provide Black or flake8 as standalone modules; the normal
repository CI remains the canonical complete environment check. No dependency
was installed to mask that host fact.

## Terminal execution evidence

The exact repair checkpoint is:

`7aa14edbdd2e484784cee6a8ec52adef4f6bf328`

Normal CI `#98`, run `30573186630`, passed on that exact SHA:

- repository job `90974843950`: complete repository verification,
  `285/285` non-visual browser checks, direct trilingual coverage, dependency
  audits and both secret lanes `PASS`; and
- visual job `90974843881`: fixed-Linux `24/24 PASS`, artifact
  `8771657987`, digest
  `334073ee8ccce3eb9ccffdd9ad005e70b477673fb27df1ccdf0b83e799aa315d`.

The single authorized controlled dispatch was CI `#99`, run `30573778175`,
on the same exact SHA. Its controlled runtime job `90976852494`:

1. passed exact tools and pinned Bench;
2. passed the fixed disposable Site/database guards;
3. installed both NPI apps and completed both migrations;
4. passed the formerly failing policy publication;
5. created the controlled document and passed immediate idempotency replay;
6. returned HTTP `500` on the first `:check-out`; and
7. removed the ephemeral containers, volumes and network.

The old shared-Datetime root is therefore repaired. The Gate is still not
PASS. Because the document-workspace assertion did not use the new sanitized
failure-detail helper, the retained log cannot uniquely identify which
checkout transaction step failed. The one authorized dispatch is exhausted.
The resulting Hard Blocker is recorded in
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-blocker.md`.
