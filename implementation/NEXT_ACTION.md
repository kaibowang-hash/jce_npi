# Next Action

Status: `P4-04 LEVEL 3 PASS — P4-05 ACTIVE`

Recovery time: `2026-07-25T09:09:22Z`

Active execution goal:
`implementation/ACTIVE_EXECUTION_GOAL.md`

The former thread-migration stop boundary is
`SUPERSEDED_BY_LATEST_USER_AUTOPILOT_AUTHORIZATION`. Continuous delivery now
proceeds automatically through P4-05 and later phases after each applicable
passing Gate. P4-04 is complete and must not be rerun merely to restore context.

Required and only development branch:
`codex/npi-v1.2-implementation`

## Controller state

- First incomplete phase:
  `3 — React App Shell Siemens UI and i18n Foundation`.
- Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; named business UAT and
  provenance-backed sanitized-data review are still externally unsigned.
- Current authorized implementation phase:
  `4 — Project Work Items and Stage Gates` (`IN_PROGRESS`).
- Completed Phase 4 atomic tasks: `P4-01`, `P4-02`, `P4-03`, and `P4-04`.
- P4-04 result: `PASS — LEVEL 3 FULL RELEASE GATE`; do not repeat its complete
  Gate.
- Current unfinished atomic task:
  `P4-05 — Live My Work, activity, and Project controls`.
- P4-05 allocation: `FR-PM-008`, `FR-PM-011`, `FR-PM-012`, `FR-CO-001`,
  `FR-CO-002`, and `FR-CO-006`.

## Completed P4-04 boundary

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
P4-04 creates no impact Domain WorkItem; P4-05 owns work projection. Complete
evidence is in `implementation/evidence/phase-4/p4-04-validation.md`.

## Passed evidence — do not repeat merely to restore context

- Final `make verify`: `PASS` — 417 Python tests, 337 frontend tests, complete
  static/type/lint/style/boundary/industrial-UI checks, coverage, production
  build, strict install-script review, and zero full/production npm audit
  findings.
- Frappe-compatible i18n: `PASS` — 1,746 literal English sources with complete
  direct `zh` and `zh-TW` coverage.
- Additive Site migration and idempotent rerun: `PASS` at exact Frappe commit
  `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`.
- Complete live Frappe runtime: `PASS` — BFF, Project, Project Work fresh,
  cross-process sealed replay, Gate Evidence, and Gate Review.
- Complete non-visual Playwright: `204/204 PASS`.
- Affected command/dialog browser lane: `26/26 PASS`.
- Forced visual update: `170/170 PASS`; immediate clean comparison:
  `170/170 PASS` at unchanged `maxDiffPixelRatio: 0`.
- Fresh Node `v24.18.0`/npm `11.16.0` target, exact dependency/install-script
  policy, and zero-vulnerability audits: `PASS`.
- Independent code/security/release review: `PASS`, with no remaining blocker,
  major, or minor finding.

Exact commands, changed-files→affected-tests mapping, repair history, review
findings, and rollback evidence are in
`implementation/evidence/phase-4/p4-04-validation.md`.

## Current unfinished atomic work

P4-05 is active. Its bounded outcome must combine:

- a live, current-user My Work projection over the already-governed Project,
  Domain WorkItem, Gate assignment, and invalidated Gate sources;
- contextual internal activity/comments/attachments without claiming mail,
  in-app delivery, portal, or external collaboration;
- honest Project health and policy-driven lifecycle controls that remain
  unavailable when the recorded production formulas, thresholds, authorities,
  or completion prerequisites are absent;
- lessons/template feedback at the boundary authorized by `FR-PM-012`; and
- complete English-source, direct `zh`, and direct `zh-TW` UI/API copy.

Production health formulas, lifecycle authorities, notification delivery,
external users, ERPNext actuals, and other scoped Class-B holds must not be
invented. Phase 3 external UAT remains unsigned and does not block the safe
NPI-owned P4-05 foundation.

## Exact recovery steps

1. Fetch `origin`, check out `codex/npi-v1.2-implementation`, and verify local
   `HEAD` equals `origin/codex/npi-v1.2-implementation` with a clean worktree.
2. Read `AGENTS.md`, `implementation/AUTOPILOT_CONTROLLER.md`,
   `implementation/PHASE_STATUS.yaml`, this file,
   `implementation/LAST_RUN.md`, `implementation/BLOCKERS.md`,
   `implementation/REQUIREMENT_TRACEABILITY.csv`,
   `implementation/DECISION_LOG.md`, `implementation/RISK_REGISTER.md`,
   `implementation/phase-4-requirement-anchor.md`,
   `implementation/evidence/phase-4/p4-04-validation.md`, and the six allocated
   requirement rows in `docs/DETAILED_REQUIREMENTS.md`.
3. Confirm P4-01 through P4-04 are complete and P4-05 is the only active Phase
   4 atomic task. Reuse the passing P4-04 evidence above.
4. Read only the P4-05-related domain/UX/API contracts and applicable
   `npi-domain-guard`, `frappe-safe-change`, `industrial-ux`, and
   `frappe-i18n` Skills; expand scope only for a material ambiguity or
   cross-domain conflict.
5. Create `implementation/evidence/phase-4/p4-05-plan.md` with exact scope,
   non-scope, Class-B holds, changed-files→tests mapping, migration/rollback,
   and truthful acceptance targets before business code.
6. Set the six P4-05 trace rows to `IN_PROGRESS_P4_05` when implementation
   actually begins, then implement the minimum complete vertical slice and use
   cumulative Level 1/2/3 validation.
7. Do not create `phase-4-gate.md` or enter Phase 5 until P4-05 and the complete
   Phase 4 Gate genuinely pass.
