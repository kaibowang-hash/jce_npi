# Next Action

Status:
`IN PROGRESS — P5-03 REQUIREMENT/DOMAIN AUDIT`

Recovery time: `2026-07-31T20:15:18Z`

Latest passed product checkpoint:
`f088d70b00b54488587b2a83a311b636ef48cf78`

Latest complete normal CI:
`30661086073` (`PASS`, exact product head SHA)

Final unchanged controlled-Site Gate:
`30661586342` (`PASS`, exact product SHA)

Required development branch:
`codex/npi-v1.2-implementation`

## Controller state

- The cumulative R1 shared Shell/design/i18n Level 3 exit Gate remains
  `PASS`; conditional R1-07 remains unactivated under `DR-REC-001`.
- Phase 5 remains `IN_PROGRESS`.
- P5-00 and P5-01 remain `PASS`.
- P5-02 is `PASS — LEVEL 2`; its final evidence is
  `implementation/evidence/phase-5/p5-02-validation.md`.
- Complete ordinary CI `30661086073` and final controlled-Site workflow
  `30661586342` passed for exact product head
  `f088d70b00b54488587b2a83a311b636ef48cf78`.
- The P5-02 recovery changed or weakened no Requirement, public API schema,
  data ownership, permission, lock, version, audit, idempotency, transaction
  order, file-integrity rule or PASS criterion.
- Production reviewer/approver policy, regulated-signature meaning, external
  identity/retrieval, scanner/viewer providers, CAD/PDM and production ERPNext
  remain explicit fail-closed holds.
- P5-03 is the only active atomic task. P5-04, P5-05 and Phase 6 remain
  inactive.
- Current trace remains 282 unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

## Current task

`P5-03 — Baseline and impact invalidation`

Requirement:

- `FR-DS-006`.

Primary boundary:

> Deliver immutable release packages/baselines containing exact released
> Document Revision, File Revision and hash references plus exact Gate
> evidence references. Only explicitly registered exact dependencies may
> create visible impact/invalidation; later revisions never replace baseline
> members and prior Gate/baseline decisions remain immutable.

Use only:

- `implementation/phase-5-requirement-anchor.md`;
- the indexed `FR-DS-006` trace row;
- the passed P5-01 exact revision/private-file boundary;
- the passed P5-02 release/confirmation/lifecycle boundary;
- the existing exact Gate evidence boundary; and
- `repo-discovery`, `npi-domain-guard`, `frappe-safe-change`, `industrial-ux`
  and `frappe-i18n` as applicable to the bounded slice.

## First incomplete action

Perform the bounded P5-03 Requirement/domain audit before changing code:

1. reconcile `FR-DS-006` with the exact P5-01/P5-02 released identities and
   the existing Phase 4 Gate-evidence resolver;
2. inventory current baseline, Gate-reference and invalidation state,
   authority, ownership, OpenAPI and UI seams;
3. freeze exact immutable package membership, version/hash lineage and
   explicit dependency-registration invariants;
4. identify all production dependency taxonomy, completeness, review and
   invalidation-authority facts that must remain held;
5. map the smallest additive vertical slice to affected tests, migrations,
   rollback and Level 2 acceptance; and
6. record the audit before implementation.

## Frozen non-scope

- Do not infer a production dependency matrix from filenames, document types,
  screenshots, test data or “latest” relationships.
- Do not rewrite or replace released revisions, File Revisions, confirmations,
  lifecycle events, baselines or prior Gate decisions.
- Do not implement EBOM revisions/comparisons; that is P5-04.
- Do not implement formal Item/MBOM publish requests or claim ERP success;
  that is P5-05/Phase 8.
- Do not activate external retrieval, CAD/PDM, production scanner/viewer or
  production ERPNext.
- Do not infer baseline or invalidation authority from Project ownership,
  RACI, `System Manager`, assignment, transport role or UI visibility.
- Do not weaken authorization-before-resolution, CSRF, optimistic versions,
  actor-bound idempotency, append-only audit/history, exact private-file
  integrity, scanner-owned truth or independent Gate authority.

## Transition

Standing automatic-delivery authority is active. Continue P5-03 through its
bounded audit, implementation checkpoints and Level 2 Task Gate without
waiting between passing internal checkpoints. Stop only for a true Class B/C
boundary that blocks every safe P5-03 slice, a required architecture/public
contract/permission/Schema/ownership change outside the frozen anchor, a
concrete security/license risk, or exhaustion of the product-root repair
budget.
