# Next Action

Status:
`IN PROGRESS — P5-02 CONTROLLED-METADATA FOUNDATION`

Recovery time: `2026-07-31T07:19:37Z`

Latest passed product checkpoint:
`5a9cd3d85885895819a730dd0da4e7abe86c2646`

Latest complete normal CI:
`30610355829` (`PASS`, exact product SHA)

Final unchanged controlled-Site Gate:
`30610747931` (`PASS`, exact product SHA)

Required development branch:
`codex/npi-v1.2-implementation`

## Controller state

- The cumulative R1 shared Shell/design/i18n Level 3 exit Gate remains
  `PASS`; conditional R1-07 remains unactivated under `DR-REC-001`.
- Phase 5 remains `IN_PROGRESS`.
- P5-00 remains `PASS`.
- P5-01 is `PASS — LEVEL 2`; its final evidence is
  `implementation/evidence/phase-5/p5-01-validation.md`.
- The final controlled-Site workflow passed its repository, controlled
  document runtime and fixed-Linux visual jobs after two migrations,
  fresh/replay/route-recovery proof and bounded cleanup.
- The P5-01 recovery changed no Requirement, OpenAPI schema, data ownership,
  DocType schema, permission, lock, version, audit, idempotency, transaction
  order, file-integrity rule or PASS criterion.
- Scoped production numbering/classification, external identity/retrieval,
  scanner/viewer provider, CAD/PDM and production ERPNext holds remain
  explicit; none is represented as active.
- The bounded P5-02 requirement/domain audit passed at
  `implementation/evidence/phase-5/p5-02-plan.md`.
- P5-02 is the only active task and is now `IN_PROGRESS_DOMAIN`; P5-03
  through P5-05 and Phase 6 remain inactive.
- Current trace remains 282 unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

## Current task

`P5-02 — Review and release workflow`

Requirements:

- `FR-DS-002`;
- `FR-DS-005`; and
- `FR-DS-010`.

Primary boundary:

> Append policy-bound review, reject, resubmit, approve, release, supersede
> and obsolete history over the exact P5-01 revision/private-file foundation,
> confirming immutable file/hash/metadata truth and failing closed when
> integrity or scanner-owned safety requirements are not satisfied.

Use:

- `implementation/phase-5-requirement-anchor.md`;
- the three indexed Requirement rows in
  `implementation/REQUIREMENT_TRACEABILITY.csv`;
- the current document/revision/file contracts and ownership declarations;
- `implementation/evidence/phase-5/p5-01-validation.md`; and
- `npi-domain-guard`, `frappe-safe-change`, `industrial-ux` and
  `frappe-i18n`.

## First incomplete action

Implement the smallest complete P5-02 controlled-metadata foundation defined
by the passed plan:

1. add the closed lifecycle states, exact synthetic release-policy model and
   fail-closed transition rules without changing the P5-01 revision snapshot;
2. add the Project-scoped policy root/version, lifecycle projection, review
   cycle, electronic confirmation and lifecycle-event DocTypes;
3. make policy/history rows publish-once or append-only, allow only the guarded
   lifecycle projection to advance, and add an independent P5-02 route switch;
4. protect an underlying Frappe `File` from deletion once its exact
   `NPI File Revision` is released; and
5. pass focused domain/controller/metadata tests before starting repository
   commands.

Do not infer production reviewer/approver roles, quorum, signature meaning,
major/minor release semantics, retention, watermark, scanner provider or
replacement/effectivity policy. Use only explicit versioned synthetic
policies in tests and fail closed when a held fact is required.

## Frozen non-scope

- Do not reopen or rewrite P5-01 revision/file/lock history.
- Do not baseline or invalidate dependencies; that is P5-03.
- Do not create EBOM revisions/comparisons; that is P5-04.
- Do not create formal Item/MBOM publish requests or claim ERP success; that
  is P5-05/Phase 8.
- Do not activate external retrieval, CAD/PDM, production scanner/viewer or
  production ERPNext.
- Do not infer authority from Project ownership, RACI, `System Manager`,
  assignment or transport role.
- Do not weaken authorization-before-resolution, CSRF, optimistic versions,
  actor-bound idempotency, append-only audit/history, exact private-file
  integrity or scanner-owned truth.

## Transition

Standing automatic-delivery authority is active. Continue the P5-02
controlled-metadata, repository/BFF/OpenAPI, workspace/runtime and Level 2
Task Gate slices without waiting between passing internal checkpoints.
Stop only for a true Class B/C boundary that blocks all safe P5-02 scope, a
required architecture/contract/permission/Schema/ownership change, a concrete
security/license risk, or five complete product-root repair rounds.
