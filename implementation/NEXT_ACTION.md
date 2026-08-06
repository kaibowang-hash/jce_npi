# Next Action

Status:
`IN_PROGRESS_DIAGNOSTIC — P5-04 CREATE STAGE`

Recovery time: `2026-08-06T03:47:13Z`

Required branch:
`codex/npi-v1.2-implementation`

Recovery checkpoint:
`2b6004750f73504705a18a8592fab843246abbd2`

## Authority

The user authorized the previously requested bounded P5-04 create-stage
diagnostic/repair sequence by asking to repair and continue the existing
Goal/Autopilot.

The sequence permits:

1. one closed response-neutral create diagnostic checkpoint;
2. affected tests and complete exact-SHA ordinary CI;
3. at most one diagnostic controlled Site;
4. one repair only when an in-scope verifier/fixture or product root is
   uniquely proven;
5. affected tests, complete ordinary CI and one final unchanged controlled
   Gate; and
6. automatic continuation only after P5-04 Level 2 passes.

It may not change Requirements, public API, permissions, Schema, ownership,
transaction order, idempotency, audit or PASS criteria.

## Current evidence

- Previous final controlled workflow `31020886002` returned only
  `P504_RUNTIME_CREATE / HttpStatusError /
  trace-f92a1e065fe35759b261601244cca7d4` after every predecessor and policy
  boundary passed.
- The closed create ladder is implemented locally. It writes only the first
  allowlisted substage, validated exception type and exact trace ID through
  the safe logger; responses and transactions are unchanged.
- Complete P5-04 EBOM tests pass `62/62`.
- Related Document diagnostic/runtime regression passes `70/70`.
- Complete tracked Python passes `958/958`; compilation and
  `git diff --check` pass.
- The diagnostic dispatch allowance remains unused (`0/1`).

## First unfinished action

Commit and push only the diagnostic/code/test/controller/evidence files, then
require complete ordinary CI on the exact SHA. The controlled P5 Site job must
remain skipped in ordinary CI. If ordinary CI passes, execute the single
diagnostic controlled-Site workflow and classify only its safe
`code / exceptionType / traceId` tuple.

P5-04 remains `IN_PROGRESS_DIAGNOSTIC`. P5-05 and Phase 6 remain inactive.

## Frozen non-scope

- P5-01 through P5-03 remain sealed `PASS`.
- NPI One owns only EBOM working revisions; ERPNext retains formal Item, MBOM,
  routing, stock UOM and execution ownership.
- No production ERPNext access, cross-database write, raw Desk product path,
  core patch, production policy default, TODO/stub or fake success is allowed.
- Existing unrelated workspace changes remain user-owned and must not be
  staged with the checkpoint.
