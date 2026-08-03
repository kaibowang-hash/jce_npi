# Next Action

Status:
`IN_PROGRESS_DIAGNOSTIC — P5-03 BASELINE CREATE RESPONSE CONTRACT`

Recovery time: `2026-08-03T02:30:57Z`

Current controller/evidence HEAD:
`a8a20ec18f5d9d16f28953f3bc100fb8728fb069`

Latest complete normal CI:
`30778815782` (`PASS`, exact controller/evidence SHA `a8a20ec`)

Additional diagnostic-only controlled-Site runs:
`30776554186` and `30777405187` (`2/2` used)

Unique repair proof:
`P503_BASELINE_CREATE_MEMBER_RELEASE_LINEAGE /
DocumentBaselineInputUnavailable /
trace-0e5e8f157cb05c66935396e6bdae896f`

P5-03 final unchanged controlled-Site Gate:
`30778190537` (`FAIL`, diagnostic activation closed)

Final safe diagnostic tuple:
`P503_BASELINE_CREATE_RESPONSE_CONTRACT / RuntimeError /
trace-062ce39fc49457a384bc1acba7afd785`

Required development branch:
`codex/npi-v1.2-implementation`

## Controller state

- P5-00, P5-01 and P5-02 remain `PASS`; P5-03 and Phase 5 remain
  `IN_PROGRESS`.
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
- P5-03 is the only current task and is `IN_PROGRESS_DIAGNOSTIC`; P5-04, P5-05 and
  Phase 6 remain inactive.
- The prior execution-authority blocker is resolved by the user's new bounded
  response-contract diagnostic authority. It permits one predicate ladder,
  at most one diagnostic-only controlled-Site dispatch and, only after unique
  proof, one response-contract-only product-root exception.
- No P5-03 `PASS` or Level 2 result is claimed.
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

Add a behavior-neutral closed predicate ladder only to
`validate_document_baseline_command`, covering project identity, replay
header, baseline shape/version/creator/global identity/snapshot hash, policy
identity/version/hash, member and file cardinality, revision identity/hash,
lifecycle version, release snapshot hash, scan state, private-path exclusion
and URL exclusion. Run affected tests and complete ordinary CI before the sole
diagnostic-only controlled-Site dispatch. Repair nothing unless the returned
allowlisted code uniquely proves one predicate.

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

## Repair accounting

`2b067c1` is the fifth completed product-root repair: the preceding safe
diagnostic uniquely proved its field-mapping root and the repair advanced the
unchanged Gate to baseline creation. The current baseline-create authority is
one extra, strictly bounded P5-03 exception. The global five-round rule is
unchanged.

The prior extra P5-03 exception was used only for repair `15abf26`; it remains
exhausted and does not alter the global five-round rule. The new authority is
separate and applies only to a uniquely proved response-contract product root.
Verifier or synthetic-fixture roots remain controller-classified non-product
repairs. P5-03 Level 2 and later Autopilot work remain inactive until the
required final unchanged Gate passes with diagnostic activation closed.
