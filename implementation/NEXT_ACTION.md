# Next Action

Status:
`BLOCKED_EXTERNAL — P5-04 CREATE-STAGE DIAGNOSTIC/REPAIR AUTHORITY`

Recovery time: `2026-08-05T15:39:03Z`

Required development branch:
`codex/npi-v1.2-implementation`

Authorized repair checkpoint:
`d21d21ad52efa2a88bc459adc43f97f265715071`

Complete ordinary CI:
[`31020190868`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31020190868)
(`PASS`, repository/E2E/Gitleaks/history and fixed-Linux visual)

Final unchanged controlled-Site workflow:
[`31020886002`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31020886002)
(`FAIL`, exact SHA `d21d21a`)

Safe result:
`P504_RUNTIME_CREATE / HttpStatusError /
trace-f92a1e065fe35759b261601244cca7d4`

## Controller state

- P5-00 through P5-03 remain sealed `PASS`; P5-04 is the only active task.
- The policy-publication blocker is resolved. Repair `d21d21a` passed local
  EBOM `58/58`, complete Python `954/954` and ordinary CI `31020190868`.
- The final Gate passed fixed Bench/Site, two migrations, unchanged
  P5-01/02/03 runtime, EBOM policy publication, empty workspace,
  guest/unrelated authorization, route recovery, visual and cleanup.
- The Gate advanced to the first EBOM create command, then returned only the
  safe aggregate result above. The former policy-publication code did not
  recur, so the repair was effective.
- `P504_RUNTIME_CREATE` is not a unique root. It spans exact policy load and
  actor authority, idempotency, root/revision/line/lifecycle persistence,
  projection save, audit, response construction and receipt sealing.
- The prior bounded repair/final-Gate authority is exhausted. No further
  diagnostic Site or product repair is currently authorized.
- P5-04 cannot pass Level 2; P5-05 and Phase 6 remain inactive.
- Trace remains 282 unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

## Current task

`P5-04 — EBOM revision and comparison`

Requirements:

- `FR-DS-011`
- `FR-DS-012`

Approved boundary:

> Deliver NPI-owned EBOM working revisions with validated hierarchy,
> quantities, alternates/effectivity fields, review/release state and
> deterministic added/removed/quantity/substitution/attribute differences.
> Do not create formal ERPNext Item/MBOM ownership or manufacturing routing.

## Single action required

Explicitly authorize one bounded P5-04 create-stage diagnostic/repair
sequence. It may add only closed response-neutral create substages, run
affected and complete ordinary CI, execute at most one diagnostic controlled
Site, repair only one uniquely proven in-scope verifier/fixture or product
root, rerun affected/ordinary CI, and reserve one final unchanged controlled
Gate. It may not change Requirements, public API, permissions, Schema,
ownership, transaction order, idempotency, audit or PASS criteria.

## Frozen invariants and non-scope

- P5-01 exact Document/File revision, lock, authorization, audit and
  idempotency truth remains unchanged.
- P5-02 immutable release lifecycle, confirmation and private-file integrity
  remains unchanged.
- P5-03 immutable baseline, Gate attachment, dependency and successor impact
  truth remains unchanged.
- NPI One owns only EBOM working revisions. ERPNext retains formal Item,
  MBOM, routing, stock UOM and execution ownership.
- No production ERPNext access, cross-database write, raw Desk product path,
  core patch, production policy default, TODO/stub or fake success is allowed.
- Existing uncommitted workspace changes remain user-owned and must not be
  staged with an Autopilot checkpoint.
