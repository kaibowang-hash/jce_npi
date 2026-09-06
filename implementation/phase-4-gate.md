# Phase 4 Gate — Project, Work Items, and Stage Gates

Status: **PASS**

Gate date: 2026-07-25

Branch: `codex/npi-v1.2-implementation`

Starting Phase checkpoint: `711b17d`

Final task starting checkpoint:
`71d628e028a7ac225df562e21ad44cd11beddb3d`

## 1. Decision

**PASS — Phase 4 is technically complete within its anchored V1.2 boundary.**

The Gate accepts P4-01 through P4-05 and automatically activates
`P5-00 — Phase 5 requirement anchor for Design, Documents, Baselines, and
EBOM`.

It does not convert Phase 3's `TECHNICAL_PASS_PENDING_UAT` into business
acceptance, install a production Project/Gate/control policy, connect
ERPNext, approve production deployment, or authorize Phase 5 product code
before P5-00 passes.

## 2. Accepted vertical slice

The Phase 4 result is:

> instantiate a Project from an immutable versioned template → manage its
> explicit team, RACI, WBS, baseline and domain work → freeze versioned Gate
> requirements and controlled evidence → review and decide a Gate against
> immutable policy/input snapshots → reopen or invalidate through a successor
> cycle with downstream denial → project the actor's exact current work →
> retain internal activity, health/lifecycle-control history and reusable
> learning in the trilingual industrial SPA

Accepted task evidence:

| Task | Result | Durable evidence |
|---|---|---|
| P4-01 — Project template and live cockpit | `PASS` | `implementation/evidence/phase-4/p4-01-validation.md` |
| P4-02 — Team, RACI, WBS, and domain work items | `PASS` | `implementation/evidence/phase-4/p4-02-validation.md` |
| P4-03 — Gate templates and controlled evidence | `PASS` | `implementation/evidence/phase-4/p4-03-validation.md` |
| P4-04 — Review, decision, snapshot, and reopen | `PASS — LEVEL 3` | `implementation/evidence/phase-4/p4-04-validation.md` |
| P4-05 — Live My Work, activity, and Project controls | `PASS — LEVEL 3` | `implementation/evidence/phase-4/p4-05-validation.md` |

P4-01 through P4-04 passing evidence was reused. It was not repeated merely
for controller recovery or the P4-05 Gate.

## 3. Final P4-05 and cumulative evidence

- 587 complete Python tests and a focused 26-test failure-semantics lane pass.
- 492 frontend unit/component tests pass under the exact Node 24/npm 11
  baseline with TypeScript, lint, formatting, style, boundary, industrial-UI,
  coverage, build, install-script and zero-vulnerability audit evidence.
- 2,221 literal English sources have complete direct `zh` and `zh-TW`
  translations.
- Additive/idempotent Site synchronization and the complete cumulative live
  Frappe runtime pass, including My Work projection rebuild/rollback,
  terminal deactivation, sealed cross-process replay, and fourteen-route
  disable/recovery.
- The complete non-visual browser matrix passes 227/227.
- The complete visual set passes a forced 188/188 regeneration followed by a
  separate clean 188/188 zero-difference comparison at unchanged tolerance.
- Original-resolution trilingual visual review covers the industrial shell,
  dense work/control surfaces, health dimensions, lifecycle prerequisites,
  proposed learning semantics, time zones, accessibility and non-color-only
  state expression.
- Independent requirement/trace, domain, permission/security,
  migration/rollback, Task Diff and release reviews report no remaining
  blocker, major or minor finding.

## 4. Requirement disposition

The 20 Phase 4 trace rows remain truthful:

- `6 TECHNICAL_VERIFIED`;
- `13 TECHNICAL_VERIFIED_FOUNDATION`; and
- `1 PARTIAL_FOUNDATION`.

The partial row is `FR-PM-004`; immutable template snapshots are proven, while
complete Project-charter/G1-baseline scope remains later work.

Foundation statuses retain their explicit open production policy, later-domain
resolver, ERP-owned, notification/external-user, scale, customization or
business-UAT boundaries. In particular:

- production template, RACI/approval, Gate, exception, invalidation, health,
  lifecycle, completion, retention and learning-governance rules remain
  scoped Class-B holds;
- My Work integration-exception sources remain Phase 8 scope;
- custom saved views, arbitrary sort/group/column personalization and
  production-scale performance are not promoted by the bounded live queue;
- the activity timeline is not claimed as the final all-domain event stream;
- notifications, external users, portal, mail and print remain undelivered;
  and
- no technical fixture or screenshot substitutes for named business UAT,
  representative sanitized-data provenance, production activation or
  ERPNext authority.

## 5. Security, ownership, migration, and rollback

- NPI One retains Project, Gate, review, internal activity, policy and derived
  My Work responsibility. ERPNext-owned formal manufacturing, item/MBOM,
  purchasing, inventory, production, formal quality, assets, maintenance,
  actual cost and finance remain outside this Phase.
- Browser access remains limited to strict same-origin NPI BFF routes.
  Authentication, CSRF, tenant, Project, exact assignment/authority,
  optimistic version, idempotency, audit and trace controls are server-side.
- No Frappe/ERPNext core code, production endpoint, credential or data was
  changed.
- Schema changes are additive and migrations install no production business
  rule or sample record.
- Before retained history, a disposable environment may restore a task
  checkpoint. After retained history, rollback disables affected routes,
  preserves immutable/additive records, fails downstream use closed and uses a
  reviewed forward fix.

## 6. External state retained

Phase 3 stays `TECHNICAL_PASS_PENDING_UAT`. Named Project Management,
Engineering/Tooling and Quality reviewers have not signed its business UAT,
and the provenance-backed sanitized representative data package is absent.
Codex cannot sign either item.

`implementation/REQUIRED_INPUTS.md` remains the single request for those
external facts and for production Project/Gate/control policy and ERPNext
reconciliation. These are scoped holds, not a global Hard Blocker for safe
NPI-owned Phase 5 work.

## 7. Automatic transition

Phase 4 is closed as `PASS`. Phase 5 becomes `IN_PROGRESS` only for:

`P5-00 — Phase 5 requirement anchor for Design, Documents, Baselines, and
EBOM`

P5-00 must allocate `FR-DS-001` through `FR-DS-014`, reconcile the M4
document/design/baseline/EBOM boundary with file and ERPNext ownership, record
Class-B holds and migration/rollback, and define the Phase 5 atomic-task order.
Only after P5-00 passes may the first product task activate:

`P5-01 — Document and design revision`

Compatibility Pack ID: `M4-01 — Document and design revision`.
