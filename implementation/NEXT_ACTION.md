# Next Action

Status:
`IN PROGRESS — P5-03 REPOSITORY/BFF/OPENAPI`

Recovery time: `2026-07-31T20:58:50Z`

Latest passed product checkpoint:
`f088d70b00b54488587b2a83a311b636ef48cf78`

Latest complete normal CI:
`30663842514` (`PASS`, P5-03 audit checkpoint `81f1249`)

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
- The P5-03 exact baseline domain, seven guarded additive DocTypes and split
  ownership passed their focused Level 1 checkpoint at
  `implementation/evidence/phase-5/p5-03-domain-metadata-checkpoint.md`.
- P5-03 is the only active task. P5-04, P5-05 and Phase 6 remain inactive.
- No active Hard Blocker exists. Production baseline contents/authority,
  dependency completeness/matrix, external providers and production ERPNext
  remain scoped fail-closed holds.
- Current trace remains 282 unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

## Current task

`P5-03 — Baseline and impact invalidation`

Requirement:

- `FR-DS-006` (`IN_PROGRESS_P5_03_FOUNDATION_VERIFIED`).

Primary boundary:

> Create immutable release packages from exact currently released Document
> Revision, File Revision and hash evidence under an independent exact
> baseline-policy authority. Attach an exact baseline through the existing
> Gate-evidence boundary. Register dependencies only at that explicit attach;
> a successor revision appends exact old/new impact lineage and refreshes the
> existing Gate Review without replacing the baseline or prior Gate history.

## First incomplete action

Implement only the P5-03 repository/BFF/OpenAPI slice:

1. add Project-scoped baseline list/create repository commands under a new
   independent fail-closed P5-03 route switch;
2. authorize transport, Project membership and exact published baseline
   policy before resolving protected Document/File facts;
3. lock and revalidate exact released revisions, lifecycle/release snapshots,
   complete Document Revision File associations and live private File truth;
4. enforce actor-bound replay/payload conflict and insert unsealed receipt,
   immutable baseline/members, audit and sealed response in the frozen order;
5. add strict BFF/OpenAPI request and safe response schemas without raw URLs,
   caller-selected scan truth or generic CRUD; and
6. prove authorization order, stale/hash/state/association/File failures,
   deterministic replay, rollback, route recovery and prior-route
   compatibility before the next focused checkpoint.

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

After repository/BFF/OpenAPI passes:

1. exact `release_baseline` Gate-evidence resolver and template kind;
2. explicit dependency registration plus successor-triggered append-only
   impact and existing Gate Review refresh;
3. dense Project Documents and Gate workspace UI with direct English/`zh`/
   `zh-TW`, accessibility and exact visuals;
4. affected tests, complete ordinary CI, one final controlled-Site Gate and
   the P5-03 Level 2 Task Gate.

Standing automatic-delivery authority remains active between passing
checkpoints. Stop only for a true controller-defined Hard Blocker.
