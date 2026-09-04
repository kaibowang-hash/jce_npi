# P5-00 Validation — Phase 5 Requirement Anchor

Validated: `2026-07-25T18:21:56Z`

Branch: `codex/npi-v1.2-implementation`

Starting and last confirmed remote checkpoint:
`028d551d4e02ad5700b165c21409e14b647babf0`

Result: **PASS — LEVEL 2 DOCUMENTATION/TRACE TASK GATE**

## 1. Scope and non-scope

P5-00 creates the Phase 5 requirement anchor, allocates
`FR-DS-001..FR-DS-014` to the Pack's five M4 atomic tasks, freezes domain and
data-ownership boundaries, records Class-B holds, and advances the controller
to P5-01.

It changes no Python, TypeScript, DocType, Schema, migration, runtime route,
OpenAPI/data-ownership contract, credential, production policy, business data,
browser surface, translation catalog, screenshot, external system or ERPNext
state. It does not claim any Phase 5 product requirement as implemented.

## 2. Requirement → task → evidence

| Requirement set | Primary task | P5-00 evidence |
|---|---|---|
| `FR-DS-001`, `003`, `004`, `007`, `008`, `009`, `014` | P5-01 | `implementation/phase-5-requirement-anchor.md` |
| `FR-DS-002`, `005`, `010` | P5-02 | `implementation/phase-5-requirement-anchor.md` |
| `FR-DS-006` | P5-03 | `implementation/phase-5-requirement-anchor.md` |
| `FR-DS-011`, `012` | P5-04 | `implementation/phase-5-requirement-anchor.md` |
| `FR-DS-013` | P5-05 | `implementation/phase-5-requirement-anchor.md` |

`ANCHORED_P5_XX` means allocated, not implemented or accepted. Later task
evidence must replace each anchored state truthfully.

## 3. Frozen implementation boundary

- Controlled Document, Document Revision and exact private File Revision are
  distinct identities. Existing `FileRevision.revision` and `released`
  semantics are not reinterpreted as the full design revision/release model.
- A raw Frappe private-file URL never grants Project access. Every
  preview/download action must reauthorize the current actor and exact object.
- Existing `NPI File Revision` deletion protection does not prove retention of
  the underlying Frappe `File`; P5-02 must enforce the released-file invariant
  at the server-side File boundary.
- NPI One owns working documents, exact revisions, baselines and engineering
  EBOM revisions. ERPNext owns formal Item Code, MBOM, stock UOM, manufacturing
  routing and execution truth.
- Actual external retrieval, real Office/CAD preview, a real CAD/PDM connector
  and actual ERPNext publishing remain unavailable/held or later-phase
  acceptance.
- The current unconstrained Execution Request payload and in-memory
  Outbox/Inbox foundation are insufficient for P5-05. Mock acceptance is never
  ERP success, and partial results cannot be summarized as complete success.

## 4. Changed files → affected checks

| Changed files | Affected checks |
|---|---|
| Phase 5 anchor and this report | required headings, exact five-task order, ownership/security/hold assertions, Markdown target existence |
| traceability CSV | parse, 173 unique IDs, exact fourteen-row allocation, source/evidence existence |
| phase/controller/recovery files | YAML parse and exact P5-00 PASS/P5-01 ACTIVE consistency |
| decision/risk/blocker/input records | scoped-hold, no-production-access and no-fake-success consistency |
| complete P5-00 diff | documentation-only path assertion, prohibited-claim scan, `git diff --check` |

## 5. Independent review

Two bounded read-only reviewers inspected the Pack allocation and current
security/data-ownership foundations.

- Requirement/trace review: no blocker, major or minor finding after the final
  allocation. It confirmed the five-task order and staged acceptance for
  external retrieval, Office/CAD preview, CAD/PDM and actual ERP execution.
- Security/ownership review: no Hard Blocker. Its required boundaries are
  incorporated: aggregate separation, live private-file revalidation,
  underlying File retention at release, independent server capabilities,
  immutable baseline/input snapshots, fail-closed external access,
  operation-specific execution requests and no optimistic ERP success.

The reviewers did not edit repository files.

## 6. Gate commands and results

The final commands and machine-readable results are captured after the complete
recovery-file update:

- safe YAML and CSV parsing: `PASS`;
- exact requirement/task/evidence assertions: `PASS`;
- anchor/ownership/hold/current-state assertions: `PASS`;
- documentation-only path assertion: `PASS`;
- referenced repository-path checks: `PASS`;
- prohibited production/fake-success claim scan: `PASS`;
- `git diff --check`: `PASS`.

No product test or runtime lane was applicable to a documentation/trace-only
task. The accepted Phase 4 Level 3 evidence remains reusable and was not
repeated.

## 7. Migration and rollback

P5-00 creates no migration or retained product data. Before Phase 5 product
history exists, a disposable environment may restore the starting checkpoint.
After retained Phase 5 records exist, rollback must disable affected routes or
dispatch, retain all immutable records and use a reviewed forward fix.

## 8. Exit

P5-00 passes its documentation/trace Task Gate. P5-01 is the sole active
atomic task. The exact P5-00 remote SHA is confirmed after commit and push and
becomes P5-01's starting checkpoint.
