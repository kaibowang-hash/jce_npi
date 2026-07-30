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

`IN_PROGRESS — BOUNDED REPAIR AUTHORIZED; NORMAL CI AND CONTROLLED-SITE GATE
PENDING`

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

## Pending terminal evidence

1. pushed exact repair checkpoint and normal CI on that SHA;
2. one unchanged `bash scripts/verify-frappe-runtime.sh --document-only`
   dispatch;
3. if and only if that passes, final Task Diff/domain/permission/security/
   UX/i18n reviews and the P5-01 Level 2 Task Gate.
