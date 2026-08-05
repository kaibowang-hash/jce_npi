# Next Action

Status:
`IN_PROGRESS — P5-04 FOUNDATION CLEAN-CI REPAIR`

Recovery time: `2026-08-05T10:06:19Z`

Required development branch:
`codex/npi-v1.2-implementation`

Latest pushed recovery checkpoint:
`a11b37379e462b3a83e75a6b49c6b6b71bb5fadd`

Latest complete ordinary CI:
`30993437267` (`PASS`, exact pushed checkpoint SHA)

Final unchanged P5 controlled-Site Gate:
`30991177478` (`PASS`, exact product SHA, diagnostics closed)

Controlled-runtime PASS artifact:
`8924223239`,
SHA-256
`6038ab3371de189330b8046e16315b19dc1f41ee8165e1da2fbfd6f2aac37153`

## Controller state

- P5-00, P5-01, P5-02 and P5-03 are `PASS` at their applicable task Gates.
- P5-03 evidence is
  `implementation/evidence/phase-5/p5-03-validation.md`.
- `FR-DS-006` is `TECHNICAL_VERIFIED` for the approved generic immutable
  baseline and explicit dependency/impact scope. Production authority,
  contents, completeness, replacement/effectivity/retention and external
  connectors remain explicit scoped holds.
- Exact-SHA ordinary CI `30990594281` passed repository, complete browser,
  fixed-Linux visual and both secret-scan lanes.
- Final workflow `30991177478` passed the unchanged controlled Document
  runtime, two migrations, exact baseline/Gate/dependency/impact/review flow,
  replay/conflict, route recovery and bounded cleanup.
- The historical P5-03 diagnostic and blocker evidence remains retained; there
  is no active Hard Blocker.
- P5-04 is the only active task. P5-05 and Phase 6 remain inactive.
- The P5-04 bounded Requirement/domain audit passed and is recorded in
  `implementation/evidence/phase-5/p5-04-plan.md`.
- The P5-04 domain/metadata foundation passed its local Level 1 checkpoint with
  focused `27/27`, adjacent P5 `201/201`, direct `3,410`-source trilingual
  coverage, compilation, JSON/YAML and diff checks. Evidence is
  `implementation/evidence/phase-5/p5-04-domain-metadata-checkpoint.md`.
- Exact-SHA CI `30995489793` isolated only the test-literal prohibited-scan
  match and the visible generated-catalog fingerprint in 18 fixed-Linux
  baselines. Both bounded evidence roots are repaired without product or Gate
  changes; a clean exact-SHA rerun remains pending.
- The trace remains `282` unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

## Current task

`P5-04 — EBOM revision and comparison`

Requirements:

- `FR-DS-011`;
- `FR-DS-012`.

Approved task boundary from the Phase 5 anchor:

> Deliver NPI-owned EBOM working revisions with validated hierarchy,
> quantities, alternates/effectivity fields, review/release state and
> deterministic added/removed/quantity/substitution/attribute differences.
> Do not create formal ERPNext Item/MBOM ownership or manufacturing routing.

## First incomplete action

Commit and push only the reviewed foundation clean-CI repair, then require the
complete ordinary workflow to pass on its exact SHA. Only after that PASS may
the controlled P5-04 repository/BFF/OpenAPI slice in
`implementation/evidence/phase-5/p5-04-plan.md` activate. Production EBOM
numbering, line identity, quantity precision, stock-UOM,
alternate/effectivity, attribute set, release authority and formal Item
conversion remain Class-B holds; install no production defaults.

## Frozen predecessor invariants

- P5-01 exact Document/File revision, lock, authorization, audit and
  idempotency truth remains unchanged.
- P5-02 released lifecycle, confirmation, private-file integrity and retained
  Frappe File truth remains unchanged.
- P5-03 exact immutable baselines, independent baseline authority, explicit
  Gate attachment/dependency registration and append-only successor impact
  remain unchanged.
- A released revision is never overwritten; retained baseline/Gate/review
  history is never deleted or silently rewritten.
- NPI One owns only EBOM working revisions in P5-04. ERPNext remains the
  authority for formal Item, MBOM, manufacturing routing, stock UOM and
  execution transactions.
- No production ERPNext access, cross-database query/write, raw DocType browser
  CRUD, core patch, production policy default, TODO/stub or fake success is
  permitted.

## Completion boundary

The audit and domain/metadata foundation checkpoints are complete with
Requirement -> Code -> Test -> Evidence and changed-files -> affected-tests
maps, scoped holds and rollback. P5-04 remains `IN_PROGRESS`; P5-05 stays
inactive until P5-04 passes its Level 2 Task Gate. Phase 5 Level 3 runs only
after P5-05 reaches the Phase boundary.
