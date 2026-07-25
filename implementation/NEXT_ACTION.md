# Next Action

Status: `AUTOPILOT RESUMED — P4-04 IN PROGRESS; NOT PASS`

Recovery time: `2026-07-25T05:48:39Z`

Active execution goal:
`implementation/ACTIVE_EXECUTION_GOAL.md`

The former thread-migration stop boundary is
`SUPERSEDED_BY_LATEST_USER_AUTOPILOT_AUTHORIZATION`. Continuous delivery now
proceeds automatically through P4-04, P4-05, and later phases after each
applicable passing Gate. P4-05 remains inactive only while P4-04 is not yet a
genuine Task/Release `PASS`.

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- First incomplete phase:
  `3 — React App Shell Siemens UI and i18n Foundation`.
- Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; named business UAT and
  provenance-backed sanitized-data review are still externally unsigned.
- Current authorized implementation phase:
  `4 — Project Work Items and Stage Gates` (`IN_PROGRESS`).
- Completed Phase 4 atomic tasks: `P4-01`, `P4-02`, and `P4-03`.
- P4-03 takeover result: `EVIDENCE_CONFIRMED`; do not repeat its complete
  Level 3 Gate.
- Current unfinished atomic task:
  `P4-04 — Review, decision, snapshot, and reopen`.
- P4-04 takeover conclusion: `DOMAIN_FOUNDATION_ACCEPTED`; this is not a Task
  Gate `PASS`.
- `P4-05` is inactive until P4-04 passes; it then starts automatically without
  another prompt.

## Completed P4-04 units

- Versioned synthetic Gate Review Policy, closed condition evaluator, explicit
  frozen review/final-decision/reopen/exception authorities, and
  parallel/sequential/conditional review domain.
- Additive controlled review persistence, live repository/controllers,
  Project→Gate→Cycle→Exception locks, actor-bound sealed idempotency,
  immutable history/audit, generic CRUD denial, and strict BFF/OpenAPI.
- Fail-closed normal pass, bounded non-P0 exception handling, exact closure
  action references, server-built immutable decisions, new-cycle reopen,
  dependency invalidation/refresh, and current-decision downstream guard.
- Compatibility repair for preserved latest-decision lineage, historical
  event schema v1 forms, legacy/exact exception request references, File
  deletion dependency scheduling, and transport capability projection.
- Live trilingual industrial Review Room with strict parsing, server-driven
  permissions, command/receipt reconciliation, immutable-history detail, and
  current loading/non-normal/command/dialog fixtures and snapshots.

No production Gate Review Policy is installed. Production approval, waiver,
invalidation, delegation, and segregation rules remain scoped Class-B holds.
P4-04 creates no impact Domain WorkItem; P4-05 owns work projection.

## Passed evidence — do not repeat merely to restore context

- P4-03 final commit:
  `0fd4762a01fd10fe6851df07ead1c5e4e7a42473`.
- P4-03 evidence blob is unchanged, and bounded reconciliation is
  `EVIDENCE_CONFIRMED` in
  `implementation/evidence/phase-4/p4-03-takeover-reconciliation.md`.
- Current P4-02/P4-03 shared repository/controller/metadata boundary:
  `46/46 PASS`.
- Gate Evidence contract/current Gate Shell boundary: `11/11 PASS`.
- Current P4-04 affected Python suite: `123/123 PASS`.
- Evidence parser, review parser, and Review Room unit/component lane:
  `116/116 PASS`.
- Generated artifacts and TypeScript: `PASS`.
- Direct changed-file ESLint, Prettier, Python compilation, JSON parsing, and
  prohibited-pattern scan: `PASS`.
- Frappe-compatible i18n audit: `1742` literal English sources with complete
  direct `zh` and `zh-TW` coverage.
- Current Gate Review/Evidence non-visual browser spec: `72/72 PASS`.
- Current affected Review Room visual matrix: `23/23 PASS` at zero pixel
  tolerance; representative normal, no-permission, and high-risk confirmation
  images were reviewed at original resolution.
- `git diff --check`: `PASS` before recovery-document updates; rerun at the
  final checkpoint boundary.

Exact commands, changed-files→affected-tests mapping, review findings, and
repairs are in:

- `implementation/evidence/phase-4/p4-03-takeover-reconciliation.md`;
- `implementation/evidence/phase-4/p4-04-takeover-review.md`.

## Current unfinished atomic work

P4-04 remains `IN_PROGRESS`. The following are not passed or waived:

- current additive Site migration and its idempotent rerun;
- focused live Frappe verification of final File-delete commit/rollback,
  legacy-history compatibility, preserved latest-decision lineage, and
  complete P4-01/P4-02/P4-03/P4-04 runtime compatibility;
- complete P4-04 module coverage, production build, npm audit, Task Diff,
  final security/permission/rollback/recovery review, and final requirement
  review;
- P4-04 Level 2 Task Gate;
- the one OpenAPI/Schema/permission/hook/shared-UI/catalog-triggered Level 3
  Full Release Gate and `release-gate` review;
- production policy inputs and Phase 3 external UAT.

The focused runtime retry at this checkpoint did not enter product execution:
the controlled MariaDB container was stopped, and `docker compose up -d`
failed with a stale OCI task (`container with given ID already exists`).
This is a local runtime prerequisite, not a product pass or product failure.
Do not reset or delete the controlled database volume to work around it.

Python Black and a standalone PyYAML parse were unavailable in the current
base Python. Do not claim those invocations passed. Direct Python compilation,
the affected Python suite, changed JSON parse, and closed OpenAPI contract
tests did pass.

## Exact recovery steps

1. Fetch `origin`, check out `codex/npi-v1.2-implementation`, and verify local
   `HEAD` equals `origin/codex/npi-v1.2-implementation` with a clean worktree.
2. Read `AGENTS.md`, `implementation/AUTOPILOT_CONTROLLER.md`,
   `implementation/PHASE_STATUS.yaml`, this file,
   `implementation/LAST_RUN.md`, `implementation/BLOCKERS.md`,
   `implementation/REQUIREMENT_TRACEABILITY.csv`,
   `implementation/DECISION_LOG.md`, `implementation/RISK_REGISTER.md`,
   `implementation/phase-4-requirement-anchor.md`,
   `implementation/evidence/phase-4/p4-03-takeover-reconciliation.md`, and
   `implementation/evidence/phase-4/p4-04-takeover-review.md`.
3. Confirm P4-03 is still the latest completed task, P4-04 is the only active
   task, and P4-05 is inactive. Reuse the passing evidence above.
4. Restore the existing MariaDB/Redis containers without resetting, deleting,
   or replacing their controlled volumes. Resolve the stale OCI task at the
   Docker runtime layer.
5. Run the additive migration and idempotent rerun, then run
   `bash scripts/verify-frappe-runtime.sh --gate-review-only`.
6. Continue only the remaining P4-04 acceptance work: one Level 2 Task Gate,
   affected repairs if any, then the single required Level 3 Gate and
   `release-gate` review.
7. Keep P4-04 `IN_PROGRESS` on any incomplete criterion. Activate P4-05 only
   after genuine P4-04 Task/Release evidence passes.
