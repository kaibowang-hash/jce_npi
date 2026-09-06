# Phase 7 Gate — Trial, Quality Collaboration and NPI Readiness

Status: **PASS — LEVEL 3**

Gate date: 2026-08-16

Branch: `codex/npi-v1.2-implementation`

Starting Phase checkpoint:
`e662684ffefd9d44c11a0e5e70e8801bd0a5f1e3`

Final product checkpoint:
`31114021cf18cf5e32c22902de5150ed2922e7ba`

## 1. Decision

**PASS — Phase 7 is technically complete within its anchored V1.2 boundary.**

The evidence-based `release-gate` review accepts P7-00 through P7-08 and
reports zero open P0, P1 or P2 finding. Standing delivery authority closes
Phase 7 and activates only `P8-00 — Phase 8 ERPNext integration requirement
anchor`.

This Gate does not approve production ERPNext access, credentials, endpoints,
formal ERP quality/asset/master-data mutation, machine acquisition, customer
signature, production reservation, automatic Gate/G7 mutation, Released Trial
Summary external event identity or production print/form/copy policy.

## 2. Accepted vertical slice

The cumulative Phase 7 result is:

> plan one Trial -> create exact immutable Round identities and input locks ->
> record manual Actuals, samples and cavities -> retain cross-Round defects,
> actions and verification -> compare exact sources and decide a conclusion ->
> evaluate versioned NPI readiness and dominant blockers -> retain handover and
> observation truth -> release an immutable NPI-owned Trial Summary and
> controlled output -> expose the same authorized Trial/Gate actions on
> phone/tablet without compressing complex engineering analysis

| Task | Result | Durable evidence |
|---|---|---|
| P7-00 — requirement anchor | `PASS — LEVEL 2` | `implementation/evidence/phase-7/p7-00-validation.md` |
| P7-01 — Trial plan and Round identity | `PASS — LEVEL 2` | `implementation/evidence/phase-7/p7-01-validation.md` |
| P7-02 — locked inputs, Actuals and samples | `PASS — LEVEL 2` | `implementation/evidence/phase-7/p7-02-validation.md` |
| P7-03 — cavity defects, actions and verification | `PASS — LEVEL 2` | `implementation/evidence/phase-7/p7-03-validation.md` |
| P7-04 — comparison, conclusion and references | `PASS — LEVEL 2` | `implementation/evidence/phase-7/p7-04-validation.md` |
| P7-05 — NPI checklist, readiness and blockers | `PASS — LEVEL 2` | `implementation/evidence/phase-7/p7-05-validation.md` |
| P7-06 — production handover and observation | `PASS — LEVEL 2` | `implementation/evidence/phase-7/p7-06-validation.md` |
| P7-07 — immutable Released Trial Summary | `PASS — LEVEL 2` | `implementation/evidence/phase-7/p7-07-validation.md` |
| P7-08 — mobile field actions | `PASS — LEVEL 2` | `implementation/evidence/phase-7/p7-08-validation.md` |

## 3. Cumulative Level 3 evidence

Final workflow `31899480493` passes the complete repository, frontend,
trilingual/i18n, vulnerability, secret, `119/119` fixed-Linux visual,
controlled preflight and cumulative disposable-Site lanes at exact SHA
`31114021cf18cf5e32c22902de5150ed2922e7ba`.

The cumulative runtime artifact `9250918326` has digest
`sha256:84bff2803a329960e6a0ebcd9f46c48d499a1d13387ef9a61b1e6b7c881840f2`.
It proves exact source/version/hash lineage, immutable successor history,
same/cross-process replay, Project-first permission/IDOR/conflict/stale
denials, independent route recovery, two migrations, redaction, zero
integration traffic and volume cleanup on pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`.

Complete exact job, artifact and digest evidence is retained in the P7-08
validation. Earlier passing task evidence was reused; it was not rewritten or
misrepresented as a fresh production test.

## 4. Requirement disposition and scoped holds

- Phase 7 NPI-owned Trial, quality-collaboration, readiness, handover,
  observation, Released Trial Summary and mobile-field requirements retain the
  exact evidence-backed dispositions in their task reports.
- `UX-020` is `TECHNICAL_VERIFIED` for the live same-authority responsive
  Trial/Gate slice.
- `FR-TR-006`, `FR-NP-006` and other ERP-dependent facts remain explicit NPI
  foundations with formal ERP projections held for Phase 8.
- `FR-INT-015` remains an NPI immutable-summary source foundation. Exact
  external event type, payload version, redaction/routing and ERP/JCE consumer
  mapping remain held by `DR-REC-009`.
- `DR-REC-003/004` continue to hold production form/signature/retention and
  browser/copy-numbering policy. No missing external input is hidden by a
  technical PASS.

## 5. Security, ownership, migration and rollback

NPI One owns its Trial and NPI collaboration truth. ERPNext remains the sole
owner of formal Customer/Supplier/Item/MBOM, manufacturing, quality, Asset,
maintenance, inventory, actual cost and finance truth. Browser traffic remains
same-origin BFF only; no cross-database access, Frappe/ERPNext core patch,
production credential, endpoint or network request was introduced.

Phase 7 Schema changes are additive and migrations passed twice on the
disposable Site. After retained history, rollback disables affected
independent routes/workspaces/workers and uses a reviewed forward fix; it does
not delete or rewrite immutable Plan/Round/input/Actual/sample/defect/
conclusion/readiness/handover/summary/File/receipt/audit history.

## 6. Automatic transition

Phase 7 is closed as `PASS — LEVEL 3`. Phase 8 becomes `IN_PROGRESS` only for
`P8-00 — ERPNext integration requirement anchor`.

P8-00 must allocate M7-01 through M7-09, reconcile `INT-001..014`, carried
Project/design/Tooling/Trial/NPI/operations requirements, `FR-INT-015`,
`FR-BR-002` and the open external-input/decision holds. It must freeze system
codes, field ownership, signed webhook/Inbox/Outbox/execution/retry/replay/
reconciliation invariants, atomic task order, rollback and affected tests.
It changes no product code and must keep Mock default, sandbox explicit and
production endpoints rejected.
