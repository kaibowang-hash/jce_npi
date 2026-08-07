# Phase 5 Gate — Design, Documents, Baselines, EBOM, and Print Foundation

Status: **PASS — LEVEL 3**

Gate date: 2026-08-07

Branch: `codex/npi-v1.2-implementation`

Starting Phase checkpoint:
`028d551d4e02ad5700b165c21409e14b647babf0`

Final product checkpoint:
`6ba2763cc14b3a044e2225d7a960ce02175f88a7`

## 1. Decision

**PASS — Phase 5 is technically complete within its anchored V1.2 boundary.**

The Gate accepts P5-00 through P5-06 and automatically activates
`P6-00 — Phase 6 Tooling requirement anchor`.

It does not approve production print forms, signatures/copy policy, a
production ERPNext/CAD/PDM connection, formal Item/MBOM execution, external
sharing, production domain policies or business UAT.

## 2. Accepted vertical slice

The Phase 5 result is:

> register a controlled input -> create exact document/file revisions ->
> review and release -> freeze an immutable baseline and Gate reference ->
> expose explicit successor impact -> create, release and compare an NPI-owned
> EBOM -> validate a no-contact formal publish request -> resolve an exact
> controlled-print mapping and retain one immutable, audited PDF output

Accepted evidence:

| Task | Result | Durable evidence |
|---|---|---|
| P5-00 — Requirement anchor | `PASS` | `implementation/phase-5-requirement-anchor.md` |
| P5-01 — Document and design revision | `PASS — LEVEL 2` | `implementation/evidence/phase-5/p5-01-validation.md` |
| P5-02 — Review and release workflow | `PASS — LEVEL 2` | `implementation/evidence/phase-5/p5-02-validation.md` |
| P5-03 — Baseline and impact invalidation | `PASS — LEVEL 2` | `implementation/evidence/phase-5/p5-03-validation.md` |
| P5-04 — EBOM revision and comparison | `PASS — LEVEL 2` | `implementation/evidence/phase-5/p5-04-validation.md` |
| P5-05 — Formal publish request | `PASS — LEVEL 2` | `implementation/evidence/phase-5/p5-05-validation.md` |
| P5-06 — Controlled print foundation | `PASS — LEVEL 2` | `implementation/evidence/phase-5/p5-06-validation.md` |

Passing earlier task evidence was reused; it was not rerun merely to rewrite
history. The terminal exact-SHA full Gate exercises the cumulative Phase 5
runtime and repository.

## 3. Cumulative Level 3 evidence

- Exact-SHA ordinary CI `31163598955` passes the complete repository, browser,
  fixed-Linux visual and both secret lanes at `6ba2763`.
- Final unchanged workflow `31164225729` passes repository job `92821257912`,
  fixed-Linux visual job `92821257937` (`68/68`) and controlled disposable-Site
  job `92821257859` with every diagnostic activation closed.
- The repository job passes `1,079` tracked Python tests, `719` frontend unit
  tests, `303` non-visual browser cases, type/lint/coverage/build, both
  zero-vulnerability audits and direct trilingual coverage for `3,889` literal
  English sources.
- The controlled job installs/migrates twice and proves the complete P5-01
  through P5-06 runtime, route disable/recovery, sealed cross-process replay,
  mutation-resistant retained output and cleanup on the pinned Frappe commit.
- Controlled, visual and secret artifacts and digests are retained in the
  P5-06 validation record.
- Independent Requirement/trace, domain, API/permission/security,
  migration/rollback, task-diff and release reviews found no open blocker,
  major or minor finding.

## 4. Requirement disposition

The Phase 5 document/design requirements retain their task validation
dispositions. In particular, production-numbering/release/sharing/provider
rules and real ERPNext Item/MBOM execution remain explicit foundations or
scoped holds rather than overclaimed completion.

`FR-PRN-001` and `FR-PRN-002` are `TECHNICAL_VERIFIED`: exact controlled-print
mapping and immutable retained-output behavior are proven. `FR-PRN-003`
remains `DECISION_REQUIRED_DR_REC_003_004`; no exact form, signer, signature,
copy numbering, retention or production delivery policy was invented.

Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; its missing named signatures and
sanitized representative-data provenance do not invalidate this bounded
technical Gate.

## 5. Security, ownership, migration and rollback

- NPI One owns engineering documents/revisions, reviews, baselines, NPI-owned
  EBOM work, publish-request truth and controlled-output snapshots. ERPNext
  retains formal Item/MBOM, routing, production, cost and execution ownership.
- Browser access remains same-origin BFF only. Tenant/Project authorization,
  independent authorities, CSRF, exact version, idempotency, audit and private
  File access are enforced server-side before protected resolution.
- No Frappe/ERPNext core, production endpoint/credential, cross-database write,
  external render/QR service or unapproved production dependency was added.
- Schema is additive; migrations install no production business policy,
  enabled mapping, source adapter or sample record.
- Before retained history, a disposable environment may restore a task
  checkpoint. After retained history, rollback disables affected routes,
  preserves immutable/additive records, fails downstream use closed and uses a
  reviewed forward fix.

## 6. Automatic transition

Phase 5 is closed as `PASS — LEVEL 3`. Phase 6 becomes `IN_PROGRESS` only for:

`P6-00 — Phase 6 Tooling requirement anchor`

P6-00 must allocate `FR-TX-001` through `FR-TX-020` and applicable UX IDs,
preserve separate Tooling Requirement/Master/Revision/physical Set identities,
reconcile NPI/ERPNext ownership and the specialized 43-column XLSX import,
record the scoped `DR-REC-002/007/008/010` holds, and define the atomic task
order, migration/rollback and changed-files-to-tests map. It installs no
Tooling product code.

Only after P6-00 passes may the first Tooling product task activate:

`P6-01 — Tooling Requirement, Master, Applicability aggregate and cockpit`

Compatibility Pack task: `M5-01`.
