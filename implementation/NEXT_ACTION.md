# Next Action

Status: `CHECKPOINT — P4-04 IMPLEMENTATION RETAINED; TASK GATE NOT PASSED`

Checkpoint time: `2026-07-24T18:54:22Z`

Required and only local development branch:
`codex/npi-v1.2-implementation`

## Controller state

- First incomplete phase:
  `3 — React App Shell Siemens UI and i18n Foundation`.
- Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`, not `PASS`; named business UAT
  and provenance-backed sanitized-data review are still unsigned.
- Current authorized implementation phase:
  `4 — Project Work Items and Stage Gates` (`IN_PROGRESS`).
- Completed Phase 4 atomic tasks: `P4-01`, `P4-02`, and `P4-03`.
- Current unfinished atomic task:
  `P4-04 — Review, decision, snapshot, and reopen`.
- `P4-05` is not active and must not start.

Phase 4 remains authorized by `implementation/phase-3-gate.md`; this does not
hide or sign the outstanding Phase 3 external acceptance.

## Retained P4-04 minimum consistent unit

This checkpoint retains the current P4-04 implementation and its directly
affected evidence:

- canonical frozen Gate input, versioned synthetic review policy, explicit
  authority bindings, parallel/sequential review, bounded exception,
  immutable decision, reopen, dependency invalidation, expiry-aware
  downstream guard, and hydration invariants;
- live Frappe repository with fixed Project→Gate→Cycle→Exception locking,
  actor-bound sealed idempotency receipts, exact authority/member checks,
  transaction rollback, immutable audit/history, IDOR-safe workspace
  hydration, and controlled transport permissions;
- strict BFF/OpenAPI command, query, and receipt surfaces with fail-closed
  input revalidation and exact decision/closure references;
- evidence/WBS/File dependency hooks that create successor review cycles and
  deny downstream use without creating a P4-04 impact Domain WorkItem;
- a live industrial Gate Review Room with strict response parsing, command
  coordination, hard-reload receipt reconciliation, actor/route isolation,
  reconstructable review/exception/decision history, and no optimistic
  success;
- `1740` literal English sources with complete direct `zh` and `zh-TW`
  catalogs, including controlled dependency-reason labels and localized
  visible action copy.

No production Gate Review Policy is installed. Production approval,
exception, invalidation, and segregation rules remain scoped Class-B holds.

The P4-04 plan overreached when it required automatic creation of an impact
Domain WorkItem. Authoritative `FR-SG-007` requires invalidation and re-review;
P4-05 owns lifecycle/work projection. The implemented P4-04 behavior therefore
records `invalidated`/`refreshed` dependency events with a nullable legacy
action reference, creates the successor cycle, and keeps downstream use denied.

## Passed evidence — do not repeat merely for handoff

The committed P4-03 Level 3 evidence remains valid and must not be restarted
because execution moves to another Codex surface:

- `make verify`: 276 Python and 237 frontend tests plus aggregate static,
  type, lint, style, boundary, UI, i18n, coverage, build, and audit checks;
- two additive/idempotent Site migrations and complete P4-01/P4-02/P4-03
  runtime;
- 153 non-visual browser cases and forced/clean 159-case exact visual
  matrices;
- original-resolution trilingual review and independent security,
  traceability, Task Diff, and release review.

Current P4-04 Level 1 evidence is also retained:

- `python -m unittest discover -s tests -p 'test_phase4_gate_review*.py' -q`:
  `116/116 PASS`;
- directly affected P4-02/P4-03 repository/controller/metadata boundary:
  `46/46 PASS`;
- focused repository lane `31/31`, runtime-verifier unit lane `11/11`, event
  controller lane `9/9`, and directly affected metadata lane `6/6`;
- `bash scripts/verify-frappe-runtime.sh --gate-review-only`: `PASS` against
  the migrated local Frappe Site, including happy path, authority/IDOR,
  replay/conflict, rollback, immutable history, receipt, reopen, and
  invalidated/refreshed successor-cycle behavior with no impact DWI;
- Gate Review parser and Review Room unit/component tests: `93/93 PASS`;
- four directly affected browser cases: `4/4 PASS` for dense audit rendering,
  committed receipt recovery, bounded absent receipt handling, and
  `requires_review`;
- three affected English/Simplified-Chinese/Traditional-Chinese Review Room
  baselines: forced update `3/3 PASS`, clean zero-tolerance comparison
  `3/3 PASS`, and original-resolution inspection complete;
- `generate:check`, TypeScript, targeted ESLint, Prettier, Stylelint, and i18n:
  `PASS`; the i18n audit reports `1740` sources and `100%` direct `zh`/
  `zh-TW` coverage;
- direct Python compilation and the relevant Black checks pass; the final
  runtime-verifier file was checked with an isolated `/tmp` Black cache;
- final recovery-document consistency checks and `git diff --check`: `PASS`.

Exact commands and the changed-files→affected-tests map are in
`implementation/evidence/phase-4/p4-04-cloud-checkpoint.md`.

## Unfinished criteria — P4-04 is not PASS

- The P4-04 Level 2 Task Gate has not run.
- The complete P4-04 state visual matrix is still pending: loading, no active
  cycle/empty, read-only, no permission, error/retry, conflict, processing,
  pending/closed exception, decided, reopened, and `requires_review`, including
  high-risk dialogs and required zoom/viewport cases.
- The complete P4-04 non-visual E2E/module test lane, coverage, production
  build, npm audit, Task Diff, security/permission review, and requirement
  review remain pending.
- Additive/idempotent migration reruns and the complete P4-01/P4-02/P4-03/
  P4-04 runtime compatibility lane remain pending for the Task/Release Gate.
- Public OpenAPI, Schema, authentication/permission, hooks, shared UI, and
  catalog changes trigger one Level 3 Full Release Gate after Level 2 is
  stable; it has not run.
- Phase 3 named-reviewer UAT and provenance-backed sanitized-data review remain
  externally unsigned.
- Production policy approval and production ERPNext access remain prohibited.

No pending item is waived, and P4-04 must not be described as `PASS`.

## Exact recovery steps

1. Fetch `origin`, check out `codex/npi-v1.2-implementation`, and verify the
   local `HEAD` equals `origin/codex/npi-v1.2-implementation` with a clean
   worktree.
2. Read `AGENTS.md`, `implementation/AUTOPILOT_CONTROLLER.md`,
   `implementation/PHASE_STATUS.yaml`, this file,
   `implementation/LAST_RUN.md`, `implementation/BLOCKERS.md`,
   `implementation/REQUIREMENT_TRACEABILITY.csv`,
   `implementation/DECISION_LOG.md`, `implementation/RISK_REGISTER.md`,
   `implementation/phase-4-requirement-anchor.md`,
   `implementation/evidence/phase-4/p4-04-plan.md`, and
   `implementation/evidence/phase-4/p4-04-cloud-checkpoint.md`.
3. Confirm P4-03 is the latest completed atomic task, P4-04 is the only active
   product task, and P4-05 is inactive. Do not rerun the passing P4-03 gate or
   the P4-04 Level 1 lanes above solely to reconstruct context.
4. Resume only the unfinished P4-04 acceptance work. First add/run the missing
   P4-04 state-specific E2E and visual fixtures, then run the complete P4-04
   Level 2 Task Gate once. Repair any failure with affected Level 1 checks
   before rerunning the Task Gate.
5. Only after Level 2 is stable, run the single triggered Level 3 Full Release
   Gate: aggregate/static/type/lint/test/coverage/build/audit, additive and
   idempotent migrations, complete runtime compatibility, full non-visual
   browser and exact trilingual visual matrices, original-resolution review,
   security/permission/rollback/recovery, traceability, Task Diff, and the
   `release-gate` Skill.
6. Activate P4-05 only if all applicable P4-04 acceptance and Gate evidence
   passes. Otherwise keep P4-04 `IN_PROGRESS` and record the exact failure.
