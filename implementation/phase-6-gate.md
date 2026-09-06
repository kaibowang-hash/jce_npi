# Phase 6 Gate — Tooling, Capacity, Controlled Import and Export

Status: **PASS — LEVEL 3**

Gate date: 2026-08-10

Branch: `codex/npi-v1.2-implementation`

Starting Phase checkpoint:
`ce401b87612c946225ef0106fb344cfdcfb21190`

Final product checkpoint:
`68f230fee73b1b6ca95206346d128e1518613d82`

## 1. Decision

**PASS — Phase 6 is technically complete within its anchored V1.2 boundary.**

The evidence-based `release-gate` review accepts P6-00 through P6-08 and
automatically activates `P7-00 — Phase 7 Trial and NPI requirement anchor`.
It found no open blocker, major or minor release finding.

This Gate does not approve production Tooling lifecycle policies, production
customer XLSX mapping, arbitrary/global export, destructive downstream
rollback, production Supplier/Asset/cost truth, ERPNext contact, official
quality authority, production acceptance approval or representative-scale
performance.

## 2. Accepted vertical slice

The Phase 6 result is:

> register why a Project needs Tooling -> retain one logical Master and exact
> Applicability -> track each physical Set -> version engineering structure ->
> expose manufacturing, defects, process and capacity truth -> retain
> acceptance evidence and prepare a no-contact Asset request -> import a
> controlled 43-column workbook with partial/retry/reconciliation truth ->
> export only an authorized selection or complete filtered object package

| Task | Result | Durable evidence |
|---|---|---|
| P6-00 — Requirement anchor | `PASS — LEVEL 2` | `implementation/evidence/phase-6/p6-00-validation.md` |
| P6-01 — Requirement, Master, Applicability and cockpit | `PASS — LEVEL 2` | `implementation/evidence/phase-6/p6-01-validation.md` |
| P6-02 — Customer-owned intake and physical Sets | `PASS — LEVEL 2` | `implementation/evidence/phase-6/p6-02-validation.md` |
| P6-03 — Revision, specification, cavities and process chain | `PASS — LEVEL 2` | `implementation/evidence/phase-6/p6-03-validation.md` |
| P6-04 — Manufacturing, supplier and ERP projection | `PASS — LEVEL 2` | `implementation/evidence/phase-6/p6-04-validation.md` |
| P6-05 — Defects, process baselines and capacity | `PASS — LEVEL 2` | `implementation/evidence/phase-6/p6-05-validation.md` |
| P6-06 — Acceptance and Asset request foundation | `PASS — LEVEL 2` | `implementation/evidence/phase-6/p6-06-validation.md` |
| P6-07 — Controlled Tooling List import | `PASS — LEVEL 2` | `implementation/evidence/phase-6/p6-07-validation.md` |
| P6-08 — Controlled Tooling List/export | `PASS — LEVEL 2` | `implementation/evidence/phase-6/p6-08-validation.md` |

Passing earlier task evidence was reused; it was not rerun merely to rewrite
history. The terminal exact-SHA Gate exercises the cumulative P5 and P6
runtime plus the complete repository and shared visual matrix.

## 3. Cumulative Level 3 evidence

- Exact-SHA ordinary CI `31355006189` passes complete repository job
  `93352955845` and fixed-Linux visual job `93352955834` at final product SHA
  `68f230f`.
- Final unchanged workflow `31355555773` passes repository `93354448586`,
  fixed-Linux visual `93354448605` (`94/94`) and cumulative disposable-Site
  runtime `93354448564`.
- The repository passes `1,420` tracked Python tests, `809` frontend unit
  tests, `352` non-visual E2E, statements `80.07%`, clean generation/type/
  lint/build, two zero-vulnerability audits, `5,753` direct trilingual sources
  and both current-tree/full-branch Gitleaks lanes.
- The controlled job installs/migrates twice and proves P5-01 through P6-08,
  same/cross-process sealed replay, permission/IDOR/conflict/stale/expiry/
  generic-mutation denials, independent route recovery, no ERP traffic and
  cleanup on the pinned Frappe commit.
- Runtime artifact `9050565297` has digest
  `sha256:2b6b91366fff2ba206bec9cfc4784472c1a4659e5eeb9dfbd2802eccbcbff222`.
  Visual and Gitleaks artifact identities/digests are retained in the P6-08
  validation report.
- Complete Requirement/trace, domain/ownership, API/permission/security,
  migration/rollback/recovery, task-diff and release reviews found no open
  finding and did not weaken a Gate criterion.

## 4. Requirement disposition

All Phase 6 requirements retain their exact task-validation disposition. The
Phase delivers verified foundations where later Trial, official quality,
approved lifecycle, production mapping or ERP execution is required; it does
not convert those holds into completion.

`UX-007` is `TECHNICAL_VERIFIED_FOUNDATION`: ten Tooling views, personal
restoration, stable paging, explicit selection/filter modes and immutable
authorized export are technically proven. Generic global editable-grid/bulk
policy and representative production-scale performance remain outside the
accepted bounded slice.

`DR-REC-002`, `DR-REC-007`, `DR-REC-008` and `DR-REC-010` remain scoped holds.
Their missing decisions do not invalidate the technical mechanisms that fail
closed around those exact boundaries.

## 5. Security, ownership, migration and rollback

- NPI One owns Tooling development/specification/version/intake/milestone/
  defect/process/capacity/acceptance/import/export truth. ERPNext retains
  formal Supplier, PO/receipt/invoice, actual cost, Asset/state/location,
  maintenance, inventory, production and finance ownership.
- Browser access remains same-origin BFF only. Tenant/Project/object authority,
  CSRF, exact version/hash, actor-bound idempotency, audit and private File
  access are server-enforced before protected resolution.
- No Frappe/ERPNext core, production endpoint/credential, cross-database write,
  arbitrary Desk export or unapproved production dependency was added.
- Schema is additive; migrations install no production lifecycle, mapping,
  adapter, customer workbook or sample business truth.
- Before retained history, a disposable environment may restore a task
  checkpoint. After retained history, rollback disables affected independent
  routes/workers/workspaces, preserves immutable records and uses a reviewed
  forward fix. It never deletes evidence to simulate reversal.

## 6. Automatic transition

Phase 6 is closed as `PASS — LEVEL 3`. Phase 7 becomes `IN_PROGRESS` only for:

`P7-00 — Phase 7 Trial and NPI requirement anchor`

P7-00 must allocate M6-01 through M6-08 and the exact Trial, quality,
readiness, handover, immutable Released Trial Summary/print and mobile-field
requirements; reconcile the Phase 6 Trial/approval holds and `DR-REC-009`;
freeze identities, ownership, lifecycle/quality/Gate authorities, atomic task
order, migration/rollback and changed-files-to-tests mapping. It changes no
product code.

Only after P7-00 passes may the first Trial product task activate:

`P7-01 — Trial plan and round lifecycle`

Compatibility Pack task: `M6-01`.
