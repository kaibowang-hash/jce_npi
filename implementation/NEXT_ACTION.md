# Next Action

Status:
`IN PROGRESS — P5-03 GATE EVIDENCE/DEPENDENCY`

Recovery time: `2026-07-31T22:22:10Z`

Latest passed product checkpoint:
`ff4fb4d15da14d6ac04354ff63d7da1af34cacba`

Latest complete normal CI:
`30669247503` (`PASS`, P5-03 repository/API checkpoint `ff4fb4d`)

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
- The Project-scoped baseline list/create repository, strict BFF/OpenAPI
  contract, direct trilingual catalog additions and refreshed fixed-Linux
  catalog baselines passed complete ordinary CI at
  `implementation/evidence/phase-5/p5-03-repository-api-checkpoint.md`.
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

Implement only the P5-03 exact Gate-evidence/dependency slice:

1. add `release_baseline` as an additive publishable Gate Template/evidence
   kind without rewriting any historical or production template snapshot;
2. retain the existing Gate attach request and its independent Gate-evidence
   authority, requiring exact baseline global ID, immutable source version `1`
   and snapshot hash;
3. revalidate the same tenant/Project immutable baseline, canonical snapshot,
   complete member rows and hashes before inserting the evidence reference;
4. return only safe baseline/member identity and hash metadata, never raw
   URLs, credentials or caller-selected dependency targets;
5. in the same existing Gate attach transaction append exactly one
   `NPI Baseline Gate Dependency` per exact baseline member with deterministic
   keys and frozen actor/request/trace identity; and
6. prove old-template compatibility, wrong Project/version/hash and member
   tamper denial, duplicate behavior, independent authority, exact dependency
   registration and full rollback before the next focused checkpoint.

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

After Gate evidence/dependency registration passes:

1. successor-triggered append-only impact and existing Gate Review refresh;
2. dense Project Documents and Gate workspace UI with direct English/`zh`/
   `zh-TW`, accessibility and exact visuals;
3. affected tests, complete ordinary CI, one final controlled-Site Gate and
   the P5-03 Level 2 Task Gate.

Standing automatic-delivery authority remains active between passing
checkpoints. Stop only for a true controller-defined Hard Blocker.
