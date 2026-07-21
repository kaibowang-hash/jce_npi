# V1.2 Autopilot Controller

## Authority and operating mode

The repository is in V1.2 continuous-delivery mode on
`codex/npi-v1.2-implementation`. After a Phase Gate is `PASS`, execution moves
to the next phase without waiting for another prompt. Product, domain,
architecture, industrial-UX, localization, security, ownership and release
rules remain mandatory. Production ERPNext must not be contacted.

The execution authority order is the latest compatible user instruction,
`AGENTS.md`, the V1.2 Execution Pack, accepted ADRs, the V1.2 DOCX completeness
check and reversible implementation choices. Pack/DOCX numbering or evidence
dimension differences are recorded in `DOCX_PACK_DEVIATIONS.md` and do not stop
work. A material conflict pauses only affected work unless it blocks everything.

## Continuous loop

For the first incomplete atomic task: read its Pack requirements and applicable
skills, map requirements to implementation and tests, implement one complete
vertical slice, run every applicable quality check, review the diff and
traceability, repair failures up to five complete rounds, run the release gate,
update evidence and controller state, commit a Phase checkpoint, push this
non-main branch and continue. A gate must never pass through skipped checks,
weakened criteria, fake data or fake success.

Only a Hard Blocker defined by the governing instruction may stop the whole
loop. Missing production ERPNext material does not block contracts, mock and
sandbox-ready adapters, tests, UI or documentation. Missing reconciliation
facts pause only formal logic that depends on those facts.

## Durable recovery protocol

1. Read `AGENTS.md`, `GOAL.md`, `PHASE_STATUS.yaml`, `QUALITY_GATE.md`, the
   traceability/blocker/decision/risk/deviation logs, the current phase gate,
   `NEXT_ACTION.md`, `LAST_RUN.md`, accepted ADRs and applicable skills.
2. Confirm the branch is `codex/npi-v1.2-implementation`; do not develop on
   `main`. Inspect Git status and preserve unrelated user changes.
3. Resume the first incomplete atomic task recorded in `NEXT_ACTION.md`; do not
   repeat work already evidenced by a passing checkpoint.
4. Before interruption, update status, next action, last run, traceability and
   evidence, then commit and push a complete recoverable checkpoint when the
   environment permits it.

## Current checkpoint

- Current phase: `3 — React App Shell, Siemens UI and i18n Foundation`.
- Current atomic task: freeze the approved Phase 3 dependency/i18n runtime facts,
  then implement the first complete industrial App Shell vertical slice.
- State at 2026-07-21T19:10:09Z: `IN_PROGRESS`.
- Latest result: Phase 1.1 passed in a fresh Debian 12 target container after
  repair round 4 corrected the post-create npm privilege/PATH defect and aligned
  Docker semantic-version checks with observed package/runtime evidence.
  The exact post-create path, `make verify-dev-environment`, `make verify` (26/26
  tests) and `git diff --check` all passed.
- Phase 3 is unpaused under the automatic-transition authorization. Production
  ERPNext remains prohibited.

See `NEXT_ACTION.md` for the single recovery action and `LAST_RUN.md` for exact
evidence.
