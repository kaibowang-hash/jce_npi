# P4-04 Final CLI-to-Cloud Handoff Checkpoint

Status: **IN PROGRESS — implementation retained; Task Gate is not PASS**

Recorded: `2026-07-24T18:54:22Z`

Starting synchronized local/remote checkpoint:
`8c35784e63261ec4aad668d043af0bd7f9eeb7bc`

Branch: `codex/npi-v1.2-implementation`

Requirements: `FR-SG-003`, `FR-SG-005`, `FR-SG-006`, `FR-SG-007`, with the
current Phase 4 contribution to `FR-SG-002`, `FR-SG-004`, and `FR-CO-006`

## Checkpoint decision

The explicit final-handoff instruction stopped new product development after
the current P4-04 minimum consistent repair batch. The checkpoint retains:

- frozen Gate inputs, versioned synthetic review policies, explicit authority
  bindings, parallel/sequential/conditional reviews, policy-bounded
  exceptions, immutable decisions, reopen/invalidation cycles, and the current
  decision guard;
- controlled Frappe persistence and a live repository with fixed
  Project→Gate→Cycle→Exception locks, sealed actor-bound idempotency receipts,
  exact member/authority resolution, IDOR-safe reads, immutable history/audit,
  rollback, and generic CRUD denial;
- strict BFF/OpenAPI query, command, and receipt routes with exact
  Project/Gate/input/cycle/version/hash/closure references and no optimistic
  success;
- controlled WBS/evidence/File dependency hooks, exact
  `invalidated`/`refreshed` events, successor review cycles, and downstream
  denial;
- a live industrial Gate Review Room with a strict closed parser, server-driven
  actions, hard-reload receipt reconciliation, actor/route isolation,
  reconstructable review/exception/decision history, and exact dependency
  lineage;
- complete direct `zh`/`zh-TW` translations for `1740` literal English
  sources and three affected trilingual normal-state visual baselines.

No production Gate Review Policy is installed. Synthetic policies exist only
in tests and disposable runtime evidence. No P4-05 work is retained.

P4-04 remains `IN_PROGRESS`. This checkpoint is not a Level 2 Task Gate or a
Level 3 Full Release Gate.

## Scope correction

The generated P4-04 plan previously required automatic creation of an impact
Domain WorkItem. That requirement is not in authoritative `FR-SG-007`, which
requires dependency invalidation and re-review. Work/lifecycle projection is
assigned to P4-05.

P4-04 therefore:

1. preserves the immutable prior decision;
2. records exact old/new dependency hashes and an `invalidated` or `refreshed`
   event;
3. creates the successor review cycle;
4. marks the Gate `requires_review` and denies downstream use; and
5. creates no impact DWI.

The action reference remains nullable only for backward-compatible reads of
legacy events. This is a plan/trace correction, not an ADR or a production
policy decision.

## Final repair batch

Independent frontend review found real checkpoint blockers. The retained batch
repairs them without expanding product scope:

- an in-flight command waits for its original request to settle across
  session/actor rotation; an uncertain result retains its receipt marker;
- another Gate's receipt is reconciled against the original Gate and cannot
  display a current-Gate success notice;
- parser invariants now bind the ordered latest decision, invalidation
  successor lineage, review actor and unique record/hash identities, review
  sequence state, non-P0 policy exception rules, requester/approver
  separation, and frozen decision/exception authorities;
- contract limits align at `8192` exception request options and `140`
  dependency-reason characters;
- Review, Exception, and Decision history displays the complete actor/time/
  opinion/hash/policy/version/closure/frozen-input rows needed to reconstruct
  the immutable record;
- dependency reason codes and visible action copy use controlled translations;
  exact step codes remain explicit identifiers and accessible names.

The focused runtime initially failed with
`Dependency-refreshed Gate workspace drifted`. The verifier still expected the
discarded impact-DWI behavior. Production code already produced the correct
successor cycles with null action references. The verifier and its unit test
were corrected; the next focused runtime passed.

The first affected visual update then found
`ENGINEERING_REVIEW` leaking into visible Chinese action copy. The visible
label was localized while the exact step identity was retained in the
accessible option name. The affected unit, E2E, mixed-language, forced visual,
and clean visual checks then passed.

## Changed files → affected checks

| Changed files | Directly affected checks |
|---|---|
| `gate_review/domain.py`, live `gate_review/frappe_repository.py`, Gate review API/BFF, controlled DocTypes, hooks, OpenAPI | 116 Gate Review Python tests; focused repository, API, contract, metadata/controller, permission, transaction, idempotency, concurrency, and dependency tests; Python compile |
| Gate evidence repository and dependency hooks | 46 directly affected P4-02/P4-03 boundary tests; focused live Gate Review runtime |
| `verify_gate_review_runtime.py` and verifier tests | 11 unit tests; isolated-cache Black; focused live runtime |
| strict frontend data source and view models | 63 parser/data-source tests; TypeScript; targeted ESLint/Prettier |
| Gate Review Room, primitives/styles, fixtures and component tests | 30 Review Room tests; targeted E2E; Stylelint; affected visual cases; original-resolution inspection |
| React command/session/receipt coordination | actor-rotation, cross-Gate receipt, committed/absent receipt, retry/conflict, and no-optimistic-success unit/E2E cases |
| translations, copy, generated catalog | `generate:check`; i18n audit; mixed-language browser/visual checks in `en`, `zh`, and `zh-TW` |
| recovery, traceability, decision, risk, blocker, anchor, and task evidence | YAML/CSV/Markdown consistency; `git diff --check` |

## Level 1 evidence

Passing historical P4-03 Gate evidence was not restarted.

| Command or review | Result |
|---|---|
| `python -m unittest discover -s tests -p 'test_phase4_gate_review*.py' -q` | `PASS — 116/116` |
| `python -m unittest tests.test_phase4_gate_evidence_repository tests.test_phase4_gate_evidence_controllers tests.test_phase4_project_work_repository_behavior tests.test_phase4_project_metadata -q` | `PASS — 46/46`; completed after the backend repair batch and not repeated for later frontend-only changes |
| focused Gate Review repository lane | `PASS — 31/31` |
| focused runtime-verifier unit lane | `PASS — 11/11` |
| focused event-controller and affected metadata lanes | `PASS — 9/9` and `6/6` |
| `bash scripts/verify-frappe-runtime.sh --gate-review-only` | `PASS` after the no-impact-DWI verifier correction; covers schema, authority/IDOR, happy path, replay/conflict, receipts, rollback, immutable history, reopen, invalidated/refreshed successor cycles, downstream rejection, and cleanup |
| `vitest run tests/unit/gate-review-data-source.test.ts tests/unit/gate-evidence-page.test.tsx` | `PASS — 93/93` |
| targeted Playwright grep for dense audit rendering, committed receipt recovery, bounded absent receipt handling, and `requires_review` | `PASS — 4/4` |
| targeted Review Room `@visual --update-snapshots=all` | `PASS — 3/3` in English, Simplified Chinese, and Traditional Chinese |
| targeted Review Room clean `@visual` comparison | `PASS — 3/3` at `maxDiffPixelRatio: 0` |
| original-resolution inspection of the same three final baselines | `PASS` for square industrial geometry, restrained palette, dense three-pane layout, single primary action, localized copy, and no visible mixed-language defect |
| `npm run generate:check` | `PASS` |
| `npm run typecheck` | `PASS` |
| targeted ESLint and Prettier | `PASS` after five direct lint repairs and final E2E formatting |
| affected Stylelint | `PASS` |
| `npm run lint:i18n` | `PASS — 1740 literal English sources; 100% direct zh/zh-TW coverage` |
| direct changed-file Python compilation | `PASS` |
| relevant production Python Black checks completed before the final frontend-only repair; `BLACK_CACHE_DIR=/tmp/npi-p404-black-cache ... black --check --workers 1 scripts/verify_gate_review_runtime.py` | `PASS`; one later combined default-cache invocation stalled and was interrupted, so no new aggregate Black claim is made |
| final YAML/CSV/recovery consistency and `git diff --check` | `PASS` |

Ruff is not installed in the local environment and is not claimed. The
focused runtime uses the migrated local Frappe v15 Site; production ERPNext was
not contacted.

## Unfinished acceptance

The following work is intentionally not represented as complete:

- the complete P4-04 state visual matrix: loading, no active cycle/empty,
  read-only, no permission, error/retry, conflict, processing,
  pending/closed exception, decided, reopened, and `requires_review`, including
  high-risk dialogs and required viewport/zoom cases;
- the complete P4-04 module/non-visual E2E lane, coverage, production build,
  npm audit, Task Diff, security/permission review, and requirement review;
- additive/idempotent migration reruns and complete P4-01/P4-02/P4-03/P4-04
  runtime compatibility;
- P4-04 Level 2 Task Gate;
- the public OpenAPI, Schema, authentication/permission, hook, shared UI, and
  shared catalog-triggered Level 3 Full Release Gate;
- Phase 3 named business UAT and provenance-backed sanitized-data review;
- production review/exception/invalidation/segregation rules and production
  ERPNext access.

No unfinished criterion is waived. P4-04 must not be labelled `PASS`.

## Exact recovery boundary

1. Fetch and check out `codex/npi-v1.2-implementation`; verify local `HEAD`
   equals the origin branch and the worktree is clean.
2. Read the durable recovery files named in `implementation/NEXT_ACTION.md`
   and this evidence file.
3. Do not repeat P4-03 or the passing P4-04 Level 1 lanes solely to restore
   context.
4. Add/run the missing P4-04 state-specific E2E and visual fixtures, then run
   the P4-04 Level 2 Task Gate once.
5. Repair any Task Gate failure with affected Level 1 checks. After Level 2 is
   stable, run the single required Level 3 Full Release Gate and update
   traceability/evidence.
6. Activate P4-05 only if all applicable P4-04 acceptance and Gate evidence
   passes. Otherwise keep P4-04 `IN_PROGRESS`.
