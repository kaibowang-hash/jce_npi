# Next Action

Status: `CHECKPOINT — P4-04 BACKEND FOUNDATION RETAINED; TASK IN PROGRESS`

Checkpoint time: `2026-07-24T09:02:26Z`

Required branch: `codex/npi-v1.2-implementation`

## Controller state

- First incomplete phase:
  `3 — React App Shell Siemens UI and i18n Foundation`.
- Phase 3 status: `TECHNICAL_PASS_PENDING_UAT` — not `PASS`.
- Current authorized implementation phase:
  `4 — Project Work Items and Stage Gates` (`IN_PROGRESS`).
- Completed Phase 4 atomic tasks: `P4-01`, `P4-02`, and `P4-03`.
- Current unfinished atomic task:
  `P4-04 — Review, decision, snapshot, and reopen`.
- `P4-05` is not active and must not start.

Phase 4 remains authorized by `implementation/phase-3-gate.md`; this does not
hide or sign the outstanding Phase 3 business UAT.

## Retained P4-04 checkpoint

The checkpoint contains a bounded backend foundation:

- canonical pure-domain Gate input, policy, authority binding, parallel/
  sequential review, exception, immutable decision, reopen/invalidation
  transition, expiry-aware downstream-guard, and hydration invariants;
- administrative versioned Gate Review Policy root/version DocTypes,
  controllers, and exact policy loader;
- controlled read-only Cycle, Review Record, Exception, Event, and Decision
  Snapshot DocTypes/controllers;
- Gate Shell `review_input_version`, review state, exact cycle/policy/decision
  references, and controlled transition validation;
- one exact, non-Desk, unassigned `NPI API User` transport-role fixture;
- seven BFF routes plus strict request validation, authentication/CSRF,
  request/trace/idempotency headers, uniform unavailable handling, closed
  OpenAPI schemas, and data-ownership declarations.

No production Gate Review Policy is installed.

This is not a live vertical slice. The API factory references the future
`npi_core.gate_review.frappe_repository`, which is deliberately absent because
the late draft was incomplete and untested. The retained review/history
DocTypes and Gate Shell remain System-Manager-only until the complete command
repository and transport DocPerms have real permission/runtime evidence.

## Passed evidence — do not repeat merely for handoff

The committed P4-03 Level 3 evidence remains valid:

- `make verify`: 276 Python and 237 frontend tests plus aggregate static,
  type, lint, style, boundary, UI, i18n, coverage, build, and audit checks;
- 20 directly affected tests after its final authorization-order repair;
- two additive/idempotent Site migrations;
- complete P4-01/P4-02/P4-03 runtime;
- 153 non-visual browser cases;
- 159 forced and clean exact visual cases;
- original-resolution trilingual review and independent security,
  traceability, Task Diff, and release review.

Do not rerun that complete P4-03 Gate solely because execution moves to
another Codex surface.

Current P4-04 Level 1 evidence is bounded and cumulative:

- pure domain: 16 focused tests pass;
- Gate Shell: 7 focused tests and 23 directly affected P4-03 metadata/
  controller regressions pass;
- policy metadata/controller/repository: 9 focused tests pass;
- review-history metadata/controller: 11 focused tests pass;
- transport-role fixture: 3 focused tests pass;
- strict API/contract slice: 17 focused tests pass;
- final affected contract trio: 29 tests pass;
- a combined 122-test affected selection initially produced 121 passes and
  one permission-metadata failure; the unverified future DocPerm/idempotency
  residue was removed and the affected metadata file then passed 11/11;
- final domain Black check and Python compilation pass;
- OpenAPI/data-ownership YAML and local `$ref` validation pass.

Exact commands and the changed-files-to-tests mapping are in
`implementation/evidence/phase-4/p4-04-cloud-checkpoint.md`.

## Known failing and unfinished criteria

- Frappe catalog generation is blocked by 265 missing direct entries in each
  of `zh` and `zh-TW` (1539 extracted sources versus 1274 catalog entries).
  This is not waived.
- The core Frappe Gate review repository, actor-bound idempotency receipt,
  fixed Project→Gate→Cycle→Exception lock order, audit/seal transaction,
  exact live member/authority resolution, IDOR-safe workspace hydration, and
  transport DocPerms are not implemented.
- Automatic dependency invalidation hooks and deterministic blocking impact
  action creation are not implemented.
- No P4-04 Site migration/runtime, live permission/CRUD denial, concurrency,
  rollback, idempotent replay, or end-to-end endpoint evidence exists.
- No live React Gate review room/data source is retained. No P4-04 component,
  browser, accessibility, trilingual, or visual evidence exists.
- P4-04 Level 2 Task Gate and its contract/Schema/auth-triggered Level 3 Full
  Release Gate have not run.
- Production approval, exception, invalidation, and segregation policy remains
  a scoped Class-B hold. Production ERPNext access remains prohibited.
- Phase 3 named-reviewer UAT and provenance-backed sanitized-data review remain
  externally unsigned.

P4-04 is `IN_PROGRESS` and must not be described as `PASS`.

## Exact recovery steps

1. Open the repository on `codex/npi-v1.2-implementation`, fetch `origin`, and
   verify local `HEAD` equals
   `origin/codex/npi-v1.2-implementation` with a clean worktree.
2. Read `AGENTS.md`, `implementation/AUTOPILOT_CONTROLLER.md`,
   `implementation/PHASE_STATUS.yaml`, this file,
   `implementation/LAST_RUN.md`, `implementation/BLOCKERS.md`,
   `implementation/REQUIREMENT_TRACEABILITY.csv`,
   `implementation/phase-4-requirement-anchor.md`,
   `implementation/evidence/phase-4/p4-04-plan.md`, and
   `implementation/evidence/phase-4/p4-04-cloud-checkpoint.md`.
3. Confirm `P4-03` remains the latest completed atomic task and that P4-04 is
   the only active product task. Do not start P4-05.
4. Resume P4-04 with one bounded repository unit: implement
   `npi_core.gate_review.frappe_repository`, actor-bound idempotency,
   minimal controlled transport DocPerms, fixed lock order, exact
   Project/member/policy/input hydration, audit/seal/rollback, and focused
   repository/permission/concurrency tests. Do not reuse the excluded partial
   draft and do not use `ignore_permissions`, `db_insert`, `set_user`, or
   nested rollback.
5. After backend source copy stabilizes, add all direct `zh` and `zh-TW`
   translations in one batch, regenerate the shared catalog, and run the
   affected i18n/mixed-language checks. Do not rely on fallback English.
6. Continue the remaining automatic-invalidation/runtime/UI units only inside
   P4-04, using Level 1 affected checks after each repair batch.
7. At complete P4-04 acceptance, run the full Level 2 Task Gate and the
   required contract/Schema/auth-triggered Level 3 once. Update traceability
   and activate P4-05 only if that evidence passes.
