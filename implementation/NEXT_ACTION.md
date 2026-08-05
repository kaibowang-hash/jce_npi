# Next Action

Status:
`IN_PROGRESS — P5-04 REQUIREMENT/DOMAIN AUDIT`

Recovery time: `2026-08-05T09:14:10Z`

Required development branch:
`codex/npi-v1.2-implementation`

Latest verified product checkpoint:
`302b1e90d3561b57d6815dca186e5c33bcb8e693`

Complete ordinary CI:
`30990594281` (`PASS`, exact product SHA)

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

Read `FR-DS-011`, `FR-DS-012`, the Phase 5 anchor, current trace, ownership
contract and existing Project/Document/baseline/Gate boundaries. Record the
P5-04 Requirement/domain audit before adding code. Freeze identity, hierarchy,
quantity/UOM/alternate/effectivity, revision lifecycle, comparison semantics,
permissions, concurrency, audit, deletion and rollback rules only where the
reconciled specifications provide facts.

If production EBOM numbering, line identity, quantity precision, stock-UOM,
alternate/effectivity, attribute set, release authority or formal Item
conversion remains unavailable, retain it as Class-B held scope and proceed
only with explicit versioned synthetic policies/fixtures. Do not infer these
rules from sample data.

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

P5-04 may advance from audit to implementation only after its plan records
Requirement -> Code -> Test -> Evidence and changed-files -> affected-tests
maps, scoped holds and rollback. P5-05 remains inactive until P5-04 passes its
Level 2 Task Gate. Phase 5 Level 3 runs only after P5-05 reaches the Phase
boundary.
