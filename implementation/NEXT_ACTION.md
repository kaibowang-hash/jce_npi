# Next Action

Status:
`IN PROGRESS — P5-03 DOMAIN/METADATA FOUNDATION`

Recovery time: `2026-07-31T20:25:22Z`

Latest passed product checkpoint:
`f088d70b00b54488587b2a83a311b636ef48cf78`

Latest complete normal CI:
`30662552535` (`PASS`, P5-02 evidence checkpoint `0681acf`)

Final unchanged controlled-Site Gate:
`30661586342` (`PASS`, exact product SHA)

Required development branch:
`codex/npi-v1.2-implementation`

## Controller state

- P5-00, P5-01 and P5-02 remain `PASS`; Phase 5 remains `IN_PROGRESS`.
- P5-02 complete evidence is
  `implementation/evidence/phase-5/p5-02-validation.md`.
- Its isolated evidence/controller checkpoint `0681acf` passed clean ordinary
  CI `30662552535` after the exact product Gate evidence was recorded.
- The bounded P5-03 Requirement/domain audit passed at
  `implementation/evidence/phase-5/p5-03-plan.md`.
- P5-03 is the only active task. P5-04, P5-05 and Phase 6 remain inactive.
- No active Hard Blocker exists. Production baseline contents/authority,
  dependency completeness/matrix, external providers and production ERPNext
  remain scoped fail-closed holds.
- Current trace remains 282 unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

## Current task

`P5-03 — Baseline and impact invalidation`

Requirement:

- `FR-DS-006` (`IN_PROGRESS_P5_03_PLANNED`).

Primary boundary:

> Create immutable release packages from exact currently released Document
> Revision, File Revision and hash evidence under an independent exact
> baseline-policy authority. Attach an exact baseline through the existing
> Gate-evidence boundary. Register dependencies only at that explicit attach;
> a successor revision appends exact old/new impact lineage and refreshes the
> existing Gate Review without replacing the baseline or prior Gate history.

## First incomplete action

Implement only the P5-03 domain/metadata foundation:

1. add strict independently testable baseline policy, baseline/member,
   dependency, impact-event and receipt domain values with canonical hashes;
2. add guarded additive DocTypes for the exact policy versions, immutable
   baseline/members, actor-bound receipt, exact Gate dependencies and
   append-only impact events;
3. make every retained record non-deletable and generic CRUD unavailable to
   normal users;
4. update data ownership with separate baseline-policy, command, rule-engine
   and Gate-review ownership;
5. prove invalid UUID/hash/state/member/order/duplicate/tamper/overwrite/delete
   cases plus deterministic canonical snapshots; and
6. stop at a focused Level 1 checkpoint before repository/API wiring.

## Frozen invariants and non-scope

- Baseline input is server-resolved and must be a current exact `released`
  revision with its exact release snapshot and complete live private
  File/hash/scan evidence. A caller cannot supply a mutable URL or “latest”.
- A baseline is immutable; later revisions never replace its members.
- Baseline creation requires a published exact Project-scoped baseline policy,
  an explicit actor binding and the existing internal command transport. No
  authority is inferred from Project owner, RACI, `System Manager`, assignment
  or UI visibility.
- Gate attachment retains its independent Gate-evidence authority and creates
  dependency registrations only for the exact attached baseline members.
- Successor creation can append an impact only for those exact registrations.
  It preserves the prior Gate evidence/decision and reuses the existing Gate
  Review invalidation/successor-cycle mechanism for resolution.
- Do not add a second impact-review state machine, infer a production
  dependency matrix, install G2/G5/G6/ECN contents or a Gate-to-baseline
  policy, or infer replacement/effectivity semantics.
- Do not implement EBOM, formal Item/MBOM publication, external retrieval,
  CAD/PDM, production scanner/viewer or production ERPNext behavior.
- Do not weaken P5-01/P5-02 revision, release, permission, integrity,
  idempotency, audit or rollback rules.

## Planned later P5-03 slices

After the foundation passes:

1. repository/BFF/OpenAPI baseline create/list and route toggle;
2. exact `release_baseline` Gate-evidence resolver and template kind;
3. explicit dependency registration plus successor-triggered append-only
   impact and existing Gate Review refresh;
4. dense Project Documents and Gate workspace UI with direct English/`zh`/
   `zh-TW`, accessibility and exact visuals;
5. affected tests, complete ordinary CI, one final controlled-Site Gate and
   the P5-03 Level 2 Task Gate.

Standing automatic-delivery authority remains active between passing
checkpoints. Stop only for a true controller-defined Hard Blocker.
