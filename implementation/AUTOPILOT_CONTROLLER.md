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

- Current phase: `4 — Project Work Items and Stage Gates`.
- Current atomic task: `P4-00` requirement anchor. Reconcile the M3 Project/Gate
  boundary, requirement allocation, domain/API/UI vocabulary, Class-B rule
  holds, acceptance evidence, migration, test, and rollback plan before
  business implementation.
- State at 2026-07-22T15:31:38Z: `IN_PROGRESS`.
- Latest result: the repaired independent Phase 3 release gate returned
  technical `PASS` with no blocking findings. Final evidence includes 110/110
  frontend unit/component tests, a clean standalone 63/63 browser run, 129/129
  force-regenerated and 129/129 exact-comparison visuals, 58/58 Python tests,
  556 direct catalog entries per locale, successful Frappe install/migrate and
  runtime verification, zero npm audit findings, and clean diff checks.
- Phase 3 is truthfully retained as `TECHNICAL_PASS_PENDING_UAT`: named business
  sign-off and provenance-backed sanitized sample review remain open but are not
  a global blocker. Phase 4 is active under automatic-transition authority.
  Production ERPNext remains prohibited, and ambiguous production rules remain
  scoped holds rather than invented defaults.

See `NEXT_ACTION.md` for the single recovery action and `LAST_RUN.md` for exact
evidence.
