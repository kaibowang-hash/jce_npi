# P4-02 Task Gate validation

Date: 2026-07-23
Decision: `PASS — LEVEL 2 TASK GATE`

P4-02 delivers the bounded Team, RACI, WBS, plan-baseline, and Domain
WorkItem vertical slice defined by the Phase 4 requirement anchor. This Task
Gate does not complete Phase 4, does not replace the later Level 3 Phase/PR
gate, and does not claim the held production RACI, lifecycle, notification, or
My Work policies.

## Changed files to affected tests

| Final change surface | Affected validation |
|---|---|
| Domain and repository behavior already present in the P4-02 checkpoint | Committed complete `make verify`; complete Project-work Python module; disposable Frappe runtime; P4-02 browser workspace |
| Cursor key resolution and authorization order | API and repository behavior tests for auth-before-validation, first-page key failure, malformed/tampered/cross-Site cursor, 503 mapping, zero item query, and no configuration auto-provision |
| Project/tenant identity and related-object checks | Repository behavior tests for same-Project/wrong-tenant identity, WBS context, related Domain WorkItem, and RACI context; disposable tenant/IDOR runtime |
| Disabled existing Project member closure | Repository behavior test proving only an identity-preserving, start-preserving, non-expansive finite end date is accepted |
| Final 1083-entry catalog hash rendered in the global App Shell | All 147 visual baselines, because every screenshot visibly contained the previous catalog hash |
| Live Team, Plan, and Work Items workspace | The complete eight-case P4-02 non-visual browser spec and six original-resolution `en`/`zh`/`zh-TW` visual cases |

The final security repair changed only
`project_work/frappe_repository.py`, `project_work_api.py`, and their focused
tests. It did not change OpenAPI, DocType Schema, migration files, frontend
source, or translation catalogs. In accordance with the cumulative validation
strategy and the user's instruction not to restart already-passing checks,
the committed aggregate evidence was retained and only the directly affected
checks were rerun. The global visual matrix was rerun because the catalog
version is visibly rendered on every case, making all 147 images directly
affected.

## Security repair closure

- Cursor signing now reads only the already-persisted per-Site
  `encryption_key`; it never calls Frappe's auto-provisioning password helper.
  Missing, malformed, non-canonical, or wrong-length configuration returns the
  documented 503 before any Domain WorkItem query, including on the first page.
- Project authorization completes before cursor key resolution or cursor
  validation. A malformed cursor cannot disclose whether an unavailable
  Project exists.
- Existing identities and related WBS, Domain WorkItem, role, RACI, and owner
  references compare both Project and tenant. Gate Shell uses the documented
  Project-root association because that additive P4-01 record has no tenant
  field.
- A disabled existing member can only be end-dated without changing identity
  or start date and without extending an existing bounded interval. Full
  production rules for disabled members' role/substitution history remain a
  Class-B hold.

## Reproducible validation

| Command / review | Result |
|---|---|
| committed `make verify` at P4-02 Cloud checkpoint | `PASS` — 211 Python and 205 frontend tests; generation, type, lint, format, style, boundaries, industrial UI, i18n, coverage, build, and both npm audits; 1083 direct source entries in each Chinese catalog |
| `python -m unittest tests.test_phase4_project_work_api tests.test_phase4_project_work_repository_behavior -q` | `PASS` — 29/29 affected API, authorization, cursor, tenant, disabled-member, idempotency, and repository behavior tests |
| `python -m unittest tests.test_phase4_project_work_repository tests.test_phase4_project_work_domain tests.test_phase4_project_work_runtime_verifier -q` | `PASS` — 34/34 adjacent repository contract, domain, graph, scale-fixture, and runtime-verifier tests |
| `make frappe-runtime-verify` | `PASS` — controlled local database identity; 1083-entry localization BFF; P4-01 regression; fresh P4-02 run `91103668221d4cf49c26143fd1237ba1`; first-write, 15 audit, 15 idempotency, graph-cycle, baseline, tenant, IDOR, concurrency, history/CRUD, all four work kinds, and separate-process sealed replay checks |
| `npm --prefix frontend run test:e2e -- tests/e2e/project-workspace-live.spec.ts --reporter=line` | `PASS` — 8/8 P4-02 live Team, Plan, and Work Items browser cases |
| non-visual Playwright shards 1/4 and 2/4 | `PASS` — 28/28 plus 28/28 supplemental live/core and trilingual non-normal-state executions |
| forced visual update, shards 1/2 and 2/2 | `PASS` — 74/74 plus 73/73; all 147 baselines regenerated with catalog `7a6aebc088501e85` |
| clean exact visual comparison, shards 1/2 and 2/2 | `PASS` — 74/74 plus 73/73 at `maxDiffPixelRatio: 0` |
| six original-resolution P4-02 images | `PASS` — Team, Plan, and Work Items across `en`, `zh`, and `zh-TW`, 1366×768 and 1920×1080, 100%–150%; square neutral industrial layout, readable dense tables, docked inspector, text-plus-shape status, and no unapproved mixed-language copy |
| Task Diff, `git diff --check`, and prohibited-pattern scan | `PASS` — no TODO/FIXME, permission bypass, direct SQL, ERPNext production access, test backdoor, or fake success |
| independent final release-gate review | `PASS` — no blocker in cursor, authorization order, tenant boundary, disabled-member closure, contracts, migration boundary, or evidence |

One attempted unsharded Playwright run was terminated by the command
orchestrator's 180-second ceiling after the Vite server received `SIGTERM`;
subsequent connection-refused messages therefore produced no product result.
The bounded spec and shard commands above completed normally. No OOM event was
recorded.

## Requirement and scope decision

- `FR-PM-005`, `FR-PM-006`, and `FR-PM-007` are technically verified
  foundations. Automatic role-driven Gate/notification assignment, production
  template generation, bulk date adjustment, and planned-versus-actual
  deviation remain outside this slice.
- `FR-PM-009` is technically verified for the bounded requirement: distinct
  risk, issue, action, and decision-request objects are related to Project
  context and queryable by Project, stage, owner, and overdue state.
- `FR-CO-002` remains a technically verified Project-scoped foundation; the
  unified My Work center and today/priority views remain assigned to P4-05.
- `FR-CO-006` remains a technically verified Phase 4 foundation. Current
  P4-02 UI/API copy has direct `zh` and `zh-TW` coverage, while later activity,
  notification, mail, print, and delivery surfaces remain with their owning
  tasks.

## Migration, rollback, and next boundary

The security repair is code-only. P4-02's additive DocTypes and migrations were
already proven by the committed aggregate and repeated real Frappe runtime.
Before retained data exists, the disposable slice can be disabled and the
P4-01 checkpoint restored. After retained history exists, keep the additive
tables and immutable records, disable affected routes, and deploy a reviewed
forward fix; do not delete Project/Gate/work history. ERPNext is unaffected
because no ERP database or production endpoint is used.

P4-02 is complete and P4-03 is activated. The next atomic task is versioned
Gate templates and controlled evidence. Phase 3 remains truthfully
`TECHNICAL_PASS_PENDING_UAT`, and the later Phase/PR boundary still requires
its complete Level 3 gate.
