# Last Run

## P4-02 recoverable in-progress checkpoint — 2026-07-23T20:00:29Z

- Branch: `codex/npi-v1.2-implementation`.
- Starting local feature checkpoint: `df14486`.
- Fast-forwarded and preserved the remote controller correction through
  `98b3f77` before restoring the P4-02 work.
- User direction: pause new product implementation after making the current
  work unit consistent; commit and push a recoverable checkpoint; do not start
  P4-03.
- Controller result: Phase 3 remains `TECHNICAL_PASS_PENDING_UAT`; Phase 4 and
  P4-02 remain `IN_PROGRESS`. This checkpoint is not a P4-02 Gate `PASS`.

### Implemented P4-02 checkpoint surface

- Added additive Project member, role assignment, dated substitution, RACI,
  WBS item/dependency/baseline, Project-work policy/idempotency, and distinct
  Domain WorkItem persistence.
- Added policy-bound Team/RACI commands, acyclic WBS/dependency updates,
  immutable plan baselines and comparison, and distinct
  `risk`/`issue`/`action`/`decision_request` creation and project/stage/owner/
  overdue queries.
- Added strict BFF/OpenAPI contracts, optimistic versioning, actor-bound
  idempotency, transaction rollback, audit, IDOR-safe authorization, protected
  history, and live Team/Plan/Work Items Project workspaces.
- Added a finite five-value policy display-label registry shared by backend,
  OpenAPI, generated TypeScript types, strict response validation, and an
  exhaustive literal `t()` switch. Unregistered labels fail closed.
- Added fresh runtime namespaces, first-write proof, separate-process sealed
  replay verification, and an exact loopback MariaDB database/account/port
  identity guard.

### Security and localization repairs completed before checkpoint

- Independent backend review reproduced a forgeable unsigned Domain WorkItem
  cursor. The repair now uses the persistent Frappe Site encryption key to
  derive a domain-separated HMAC-SHA256 key; the MAC covers version, query
  fingerprint, `asOf`, `dueAt`, and `globalId`. Forgery, field/signature
  tampering, and another Site key return 422 before item queries; missing or
  invalid signing configuration fails closed as a distinct 503. Project
  authorization still precedes cursor validation.
- Replaced all affected positional backend translation placeholders with named
  placeholders, extended static extraction to reject positional placeholders,
  and required named placeholder parity in both Chinese catalogs.
- Independent frontend review found no release-blocking issue in the live BFF,
  response validation, owner normalization, finite-label translation,
  non-normal states, accessibility, 150% layouts, or industrial styling.

### Incremental verification

| Command / review | Result |
|---|---|
| focused Project/P4-02 Python suite | `PASS` — 98/98 domain contract API metadata policy repository security and runtime-verifier tests |
| frontend generated-artifact check and TypeScript | `PASS` |
| frontend i18n audit | `PASS` — 1083 literal English sources with 100% direct `zh` and `zh-TW` coverage |
| focused frontend unit/component suite | `PASS` — 57/57 copy data-source and workspace tests |
| `git diff --check` | `PASS` |
| `make frappe-site-init` | `PASS` — controlled `npi_one_runtime` identity plus idempotent Frappe migrate at `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` |
| first `make frappe-runtime-verify` after catalog edit | `FAIL` — the disposable Site still had the previous effective translation catalog and language mutation returned the expected fail-closed 503 |
| migrate/clear-cache then identical `make frappe-runtime-verify` | `PASS` — 1083-entry BFF catalogs; P4-01 runtime; fresh P4-02 namespace; concurrency; cycle/history/CRUD/IDOR guards; HMAC cursor tamper rejection; and separate-process sealed replay |

The final successful P4-02 runtime used fresh run ID
`8ab0cfb9efca4ac2b0ad56c1ad8211ce`, proved every namespaced fixture absent
before its first write, recorded 15 audit and 15 idempotency records, rejected
both graph-cycle attacks, retained all four Domain WorkItem kinds, verified the
baseline hash, produced one optimistic-concurrency conflict and one winner,
and replayed the sealed `project.team.configure` response in a separate
process.

One direct Vitest attempt was invoked from the repository root rather than
through the frontend npm script, so it did not load the jsdom/setup
configuration and failed. The exact focused suite was immediately rerun through
`npm --prefix frontend run test:unit -- ...` and passed 57/57; this was a
command-context error rather than a product-test failure.

### Deliberately open before P4-02 Gate

- The complete aggregate `make verify` has not been rerun after the final HMAC
  and named-placeholder repairs.
- Non-visual Playwright was not rerun after the pause instruction.
- The earlier 147-case forced visual generation predates the final 1083-entry
  catalog. Because the rendered catalog hash changed, all 147 cases require a
  new forced regeneration followed by zero-difference comparison and
  representative original-resolution review.
- Final P4-02 evidence and the independent `release-gate` decision are not
  complete. Requirement rows therefore use pending-gate/foundation states.
- No Hard Blocker exists. Delivery is paused by explicit user direction, and
  P4-03 has not started.

## Controller state correction — 2026-07-23T08:06:04Z

- Confirmed the repository state at `df14486` and renamed the local branch from
  the environment-provided `work` name to the required
  `codex/npi-v1.2-implementation` name.
- Persisted the 2026-07-23 controller additions in
  `AUTOPILOT_CONTROLLER.md` and made that controller mandatory in `AGENTS.md`.
- Re-read `PHASE_STATUS.yaml`, `QUALITY_GATE.md`, `phase-3-gate.md`, the Phase 3
  traceability rows, `NEXT_ACTION.md`, and recent commits. Phase 3 is the first
  non-`PASS` phase and remains `TECHNICAL_PASS_PENDING_UAT`; `FR-UX-031` remains
  `PENDING_BUSINESS_UAT_AND_SANITIZED_DATA`.
- The Phase 3 Gate contains the exact Pack-approved exception that permits
  continuation: its technical release gate passed, the external UAT/data item
  is not a global blocker, and it explicitly activates Phase 4. P4-02 is thus
  the next safely executable Cloud task, not the first incomplete requirement.
- Phase 1.1 `PASS` is supported by the committed fresh-Codespaces dynamic
  evidence in `phase-1.1-gate.md`. This Cloud host's unavailable Docker and
  registry HTTP 403 are environment-specific limitations; they neither
  overwrite that evidence nor constitute a new validation result.
- No product feature was implemented in this correction. `git diff --check`
  passed; the next action now exposes both the earlier external Phase 3 task and
  the separately authorized Cloud-executable Phase 4 task.

- Timestamp: `2026-07-23T03:20:38Z`
- Branch: `codex/npi-v1.2-implementation`
- Starting HEAD: `24e901d8b908`
- Starting upstream state: ahead 0 / behind 0
- Atomic task: `P4-01 — Project template and live cockpit vertical slice`
- Result: `PASS`
- Current phase: `4 — Project Work Items and Stage Gates`
- Next task: `P4-02 — Team, RACI, WBS, and domain work items`

## P4-01 outcome

- Added generic versioned Project templates and nine additive persistence
  DocTypes without installing a production default.
- Added a strict domain service and Frappe repository that atomically creates
  a draft Engineering Project plus G0/G1 shells from an exact immutable
  published-template snapshot.
- Enforced tenant-scoped explicit business codes, stable UUID identity,
  expected version, actor-bound idempotency, rollback-safe races, audit, CSRF,
  closed request fields, correlated request/trace IDs, and controller guards
  for children and controlled history.
- Added strict create/query Project contracts and live BFF routes under
  `/api/npi/v1`, with owner/System Manager authorization and IDOR-safe
  not-found behavior.
- Switched the accepted Project cockpit path to the live BFF while retaining
  the fixture only as an explicit demo. Normal and required non-normal states
  pass in `en`, `zh`, and `zh-TW`.
- Kept FR-PM-001, FR-PM-003, and FR-PM-004 at truthful partial/foundation
  status; production deliverables/roles/duration, complete required-reference
  policy, charter fields, and the formal immutable G1 baseline remain future
  work.

## Verification

| Command / review | Result |
|---|---|
| `make verify` | `PASS` — 120/120 Python tests, 153/153 frontend tests, static/type/style/boundary/UI/i18n checks, coverage, build, and both npm audits |
| `npm --prefix frontend run test:e2e` | `PASS` — 103/103 non-visual Chromium tests |
| `npm --prefix frontend run test:visual:update` | `PASS` — 141/141 forced baseline generation |
| clean exact visual comparison | `PASS` — native Playwright shards 71/71 + 70/70 at `maxDiffPixelRatio: 0` |
| three-image live Project manual review | `PASS` — English, Simplified Chinese, and Traditional Chinese at original resolution |
| `make frappe-site-init` plus idempotent rerun | `PASS` — Frappe 15.115.4 at `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` |
| `make frappe-runtime-verify` | `PASS` — live create/query, permissions, CSRF, sequential idempotent replay/conflicts, audit, mutation guards, localization, and cleanup; aggregate adapter tests cover race rollback/reload |
| prohibited-pattern and whitespace review | `PASS` |

The final aggregate retains 738 literal English sources with complete direct
`zh` and `zh-TW` coverage. Coverage is 93.63% lines/statements, 91.23%
branches, and 91.05% functions. The production build transformed 392 modules;
the main JavaScript asset is 789.33 kB minified / 199.73 kB gzip, so R-010
remains open. Both npm audits found zero vulnerabilities.

The real Frappe Project runtime created exactly two Gate shells, replayed an
identical command without duplication, returned 409 for changed idempotency
payload and business-code/version conflicts, returned 403 for tenant mismatch,
returned 404 for IDOR, denied generic Project CRUD, denied nine standalone
child mutations and seven history deletes, recorded one audit event, and
confirmed that no template is installed by migration.

Complete evidence is in
`implementation/evidence/phase-4/p4-01-validation.md`. Phase 4 remains
`IN_PROGRESS`; P4-02 is active under the automatic-transition authority.
