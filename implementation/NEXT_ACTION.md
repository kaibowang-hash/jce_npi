# Next Action

Status:
`IN_PROGRESS — P5-04 FRONTEND WORKSPACE`

Recovery time: `2026-08-05T11:35:29Z`

Required development branch:
`codex/npi-v1.2-implementation`

Latest pushed recovery checkpoint:
`40e7b7036b9f39a8298b6bb44df9749c75337c5e`

Latest complete ordinary CI:
`31001529719` (`PASS`, exact pushed checkpoint SHA)

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
  baselines. Both bounded evidence roots were repaired without product or Gate
  changes, and exact-SHA CI `30996305240` passed complete repository,
  `288/288` browser, fixed-Linux `59/59` and both secret lanes.
- The repository/BFF/OpenAPI candidate passes local Level 1: P5
  Document/EBOM `217/217`, tracked Python `939/939`, frontend unit `671/671`,
  TypeScript, complete lint, production bundle, OpenAPI/YAML, reconciliation,
  direct `3,421`-source trilingual coverage, prohibited-pattern and diff
  checks. Evidence is
  `implementation/evidence/phase-5/p5-04-repository-api-checkpoint.md`.
- That candidate is not a stage PASS until complete ordinary CI passes its
  exact pushed SHA. The frontend workspace therefore remains inactive.
- Exact-SHA CI `31000405445` passed repository job `92287612411`, including
  complete verification, non-visual browser and both secret lanes. Visual job
  `92287612467` alone passed `41/59` and isolated exactly the eighteen durable
  1440x900 P0 images whose bottom catalog fingerprint changed from
  `18fefcf811fde25b` to `e24def7bfc10bf59`.
- Artifact `8928055413`, digest
  `sha256:0528cc2c344c1ed79a794727b543607a991a4aeca85e0c03e0431a43eb105b1e`,
  was reviewed. Every strong delta is `256` pixels in the status bar; no
  product-workspace pixel changed. Its eighteen actuals are accepted
  byte-for-byte only as their corresponding fixed-Linux baselines.
- Repair checkpoint `40e7b70` then passed complete unchanged ordinary CI
  `31001529719`: repository `92291319560`, fixed-Linux `92291319718`
  (`59/59`), complete non-visual browser and both secret lanes all passed.
  The repository/BFF/OpenAPI stage is closed.
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

Implement and test only the P5-04 Project EBOM frontend workspace defined in
the audited plan: strict data source and view models, dense industrial
revision/line/comparison views, exact submit/review/release command handling,
normal/empty/loading/no-permission/read-only/error/conflict/processing states,
accessibility and direct English/zh/zh-TW coverage. Production EBOM numbering,
line identity, quantity precision, stock-UOM, alternate/effectivity, attribute
set, release authority and formal Item conversion remain Class-B holds;
install no production defaults. Controlled runtime, P5-05 and Phase 6 remain
inactive.

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
