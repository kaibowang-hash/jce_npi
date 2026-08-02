# Next Action

Status:
`IN_PROGRESS_DIAGNOSTIC — P5-03 BASELINE CREATE`

Recovery time: `2026-08-02T19:11:28Z`

Recovered base HEAD:
`a1d84294641cb0b8cf71002c3d3557cb6b485ce7`

Latest complete normal CI:
`30761151383` (`PASS`, exact recovery-base SHA `a1d8429`)

Diagnostic-only controlled-Site run:
`30761455482` (`FAIL`, safe diagnostic evidence only)

Safe diagnostic tuple:
`P503_VERIFIER_POST_WORKSPACE_BASELINE_CREATE / RuntimeError /
trace-f9c9295e07be5bec93aa8b6b05cc2c30`

P5-03 final unchanged controlled-Site Gate:
`NOT EXECUTED`

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
- P5-03 is the only active task and is explicitly
  `IN_PROGRESS_DIAGNOSTIC`; P5-04, P5-05 and Phase 6 remain inactive.
- No active Hard Blocker exists. Production baseline contents/authority,
  dependency completeness/matrix, external providers and production ERPNext
  remain scoped fail-closed holds.
- No P5-03 `PASS` is claimed. Its final unchanged controlled-Site Gate has not
  run.
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

Add one behavior-neutral, closed diagnostic ladder around the existing
baseline-create path only:

1. server stages: command context, input parse, Project lock, membership
   authority, policy load, idempotency replay, member resolve, domain build,
   receipt insert, baseline insert, member insert, audit append, response
   build and receipt seal;
2. verifier stages: client HTTP, response shape and response contract; and
3. output only an allowlisted stage code, validated exception type and the
   exact trace ID. Never output exception text, traceback, request, response,
   Cookie, credential, business data or storage path.

Run affected tests and complete ordinary CI before each of at most two newly
authorized diagnostic-only dispatches. Diagnostic convergence does not count
as a product-root repair. Once one unique server root is proved, cross-check
it against `FR-DS-006`, the Requirement anchor, OpenAPI, real DocType fields,
permissions and transaction invariants, then repair only that root.

After the repair, run affected tests, complete ordinary CI and one final
unchanged controlled-Site Gate with the diagnostic activation path closed. If
two diagnostic dispatches cannot prove one root, or the repair would alter a
business rule, API, permission, Schema, data ownership or transaction order,
stop and record one blocker without guessing.

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

After the final unchanged Gate passes, update P5-03 controller/evidence and
continue the existing P5-03 Level 2 Task Gate and V1.2 Autopilot.

Standing automatic-delivery authority remains active between passing
checkpoints. Stop only for a true controller-defined Hard Blocker.
