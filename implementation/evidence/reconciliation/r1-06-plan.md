# R1-06 Plan — Controlled undo prototype gate and 1440 visual governance

Date: 2026-07-30
Branch: `codex/npi-v1.2-implementation`
Task: `R1-06 — Controlled undo prototype gate and 1440 visual governance`
Requirements: `UX-026`, `UX-030`, `UX-035`, `UX-036`
Status: `IN_PROGRESS — STAGE 0 PASS; STAGE 1 PROTOTYPE READY`
Starting synchronized bridge checkpoint:
`373770f988b4cf7707b41a50e96b7a4861d93c3b`

## Delivery sequence

### Stage 0 — requirement anchor and atomic plan

- Commit the exact requirement, eligibility, ineligibility, approval, visual
  registry, trace and validation boundaries before product code.
- Record that no approved My Work business bulk command exists and that the
  full `UX-026` bulk-status acceptance remains held.
- Select only the current actor's closed-view My Work grid-layout reset as the
  low-risk prototype candidate.
- Keep Product Owner approval externally owned and define independent work that
  can continue while it is pending.

Exit: documentation/trace consistency checks pass and the checkpoint is pushed.

Validation:
[R1-06 Stage 0 Validation — Requirement anchor and atomic plan](r1-06-stage-0-validation.md).

### Stage 1 — clickable reset/undo prototype and approval package

- Add a deterministic, non-production prototype entry over the existing My
  Work grid showing reset confirmation, server-confirmed undo availability,
  bounded countdown, processing, success, expiry, conflict, permission denial,
  retryable failure and final failure/recovery.
- Use a complete literal-English source set with direct `zh` and `zh-TW`
  translations. Preserve keyboard access, visible focus, status text/icon,
  non-color-only meaning and one page primary action.
- Keep the prototype transport explicit and synthetic. It cannot call or
  simulate a successful production mutation.
- Add a versioned prototype approval manifest whose state is initially
  `PENDING_PRODUCT_OWNER`. The repository verifier must reject a transition to
  backend implementation unless the manifest contains an actual dated
  approval tied to the reviewed prototype revision and policy facts.
- Produce a review package with route/story, state inventory, three-language
  screenshots, accessibility results, eligible/ineligible actions, proposed
  duration and consequence/recovery copy.

Exit: technical prototype evidence may pass, but the stage records approval as
pending until supplied by the Product Owner. Codex never signs it.

### Stage 2 — approved fixed reset/undo command vertical slice

Entry: only an actual Stage 1 Product Owner approval record.

- Extend the fixed My Work grid-preference boundary with one reset command and
  one matching undo command. Do not expose a generic command name, storage key,
  actor, tenant, grid, schema or arbitrary preference payload.
- Add immutable/audited reset/undo command truth, including canonical
  before/after hashes and snapshots, preference versions, token digest,
  expiry, consumption, idempotency, actor and request/trace lineage.
- Validate trusted CSRF, authenticated actor, closed view/schema, optimistic
  current version/hash, expiry, one-time consumption and corrupt-state
  handling. Lost responses reconcile; they never auto-replay or display
  optimistic success.
- Restore as a new preference version; never overwrite history. Generic Desk
  CRUD and cross-user/cross-tenant access remain denied.
- Integrate the confirmed command with the existing My Work grid UI and remove
  the prototype-only seam only after equivalent real states pass.

This public API/schema/shared-UI boundary triggers a task-level Level 3 Gate in
addition to the cumulative R1 exit Gate.

If approval remains pending, Stage 2 stays scoped-held. The task continues to
Stage 3 without claiming `UX-026` backend completion.

### Stage 3 — durable additive 1440 P0 visual governance

- Make the current P0 registry an explicit machine-checked source for
  `work`, `project`, `gate`, `tooling`, `trial` and `execution`.
- Add exactly 18 normal-state cases at 1440×900/100%:
  six screens × `en`/`zh`/`zh-TW`.
- Add density assertions for visible object context, primary action,
  work surface/list and applicable properties/inspector with no document-level
  overflow.
- Preserve every existing 1366×768, 1920×1080, zoom, scenario and tablet case.
- Replace the temporary R1-05 affected-visual CI command with durable,
  fixed-digest Linux governance that verifies the 1440 cross-product and
  retains the previously accepted R1-05 affected cases.
- Upload bounded reports/results/diff artifacts even on comparison failure and
  verify the CI workflow, digest, expected cases and artifact retention in the
  repository verifier.
- Generate only missing R1-06 baselines, run a clean exact-zero comparison, and
  inspect representative original-resolution images in all three languages.
  Do not normalize unrelated historical drift.

Stage 3 is independent of Stage 2 Product Owner approval.

### Stage 4 — R1-06 Task Gate and cumulative R1 exit Gate

- Run the R1-06 Level 2 Task Gate over all completed stages.
- If Stage 2 changed public API/schema/shared UI, run its triggered complete
  Level 3 evidence; otherwise record the scoped approval hold precisely.
- Evaluate `DR-REC-001`. If still unapproved, skip conditional R1-07 without
  relabeling it complete.
- Run the mandatory cumulative R1 shared Shell/design/i18n Level 3 release
  gate using the `release-gate` Skill and all required repository, runtime,
  security, migration/rollback, trilingual, browser, visual, trace and
  independent review evidence.
- Only a passing cumulative exit Gate releases P5-01. An unsigned Product Owner
  approval holds only Stage 2 and the exact dependent trace claim unless the
  controller's exit criteria explicitly require it.

## Requirement to code, test and evidence

| Requirement | Planned code/governance | Required tests | Evidence |
|---|---|---|---|
| `UX-026` | Closed personal grid reset/undo prototype; approved fixed command only; explicit ineligible recovery | prototype state/accessibility/i18n; if approved, domain/repository/API/permission/idempotency/conflict/expiry/consumption/reconciliation/runtime/browser tests | prototype review package; approval record or truthful scoped hold; command Gate if activated |
| `UX-030` | Versioned prototype approval manifest and fail-closed task-entry verifier | missing/pending/malformed/wrong-revision/fabricated approval rejection; approved fixture only in verifier tests; repository backlog coverage | prototype manifest validation and actual Product Owner approval status |
| `UX-035` | 1440 density assertions over current P0 registry | six-page × three-language geometry/overflow/context/action/work/properties cases; accessibility | original-resolution trilingual review and exact Linux results |
| `UX-036` | Explicit 18-case 1440 cross-product; fixed-digest CI; diff artifacts; legacy-matrix preservation verifier | registry completeness, expected-name set, CI/digest/artifact guard, exact clean screenshots, complete existing visual regression | workflow run/jobs/artifact IDs, hashes, screenshot manifest and review |

## Expected files

Stage 1 may touch:

- `frontend/src/components/live-my-worklist.tsx` or a bounded prototype wrapper;
- a repository-owned reset/undo prototype state adapter;
- affected styles and local icon/action adapter consumers;
- frontend unit/component/E2E prototype tests;
- Frappe-compatible translation catalogs;
- a versioned prototype approval manifest and verifier/tests.

Stage 2, only after approval, may touch:

- `apps/npi_core/npi_core/grid_personalization/`;
- the fixed grid-personalization API/controller/BFF and OpenAPI contract;
- one additive command/audit DocType boundary;
- frontend My Work data source/controller and affected tests;
- runtime/migration/recovery verification.

Stage 3 may touch:

- `frontend/tests/e2e/support.ts`;
- `frontend/tests/e2e/visual-matrix.spec.ts` or a bounded governed companion;
- Linux snapshot directories for the exact new cases;
- `.github/workflows/ci.yml`;
- repository verifier scripts/tests;
- R1-06 evidence and controller state.

The file list may contract after reuse inspection. It may not expand into a
generic preference/undo service, business bulk commands, unrelated module
retrofits, product-authority mapping or bulk historical baseline rewrite.

## Changed-files to affected-tests

| Changed boundary | Affected checks |
|---|---|
| Anchor/plan/controller Markdown/YAML | exact requirement/trace/backlog/status consistency; YAML parse; `git diff --check` |
| Prototype state adapter and My Work prototype consumer | focused unit/component tests; finite-state and no-fake-success checks; keyboard/focus/axe; trilingual E2E and affected visual cases |
| Prototype approval manifest/verifier | pending/missing/malformed/revision mismatch/required-field tests; repository verifier; synthetic approved test fixture cannot mutate the real manifest |
| Translation source/catalog changes | catalog extraction/check, direct `zh`/`zh-TW` coverage, terminology and mixed-language scans; affected pages in all locales |
| Fixed reset/undo API/schema, if approved | domain/repository/controller/API/OpenAPI; guest/CSRF/IDOR/cross-tenant/closed-input/version/hash/expiry/consumption/idempotency/lost-response/generic-CRUD denial; migrations and controlled Frappe runtime |
| My Work real-command integration, if approved | existing grid preference/controller units; reset/undo normal/conflict/expired/denied/retry/reload cases; R1-04/R1-05 affected regressions |
| P0 registry and 1440 visual spec | exact 18-case set, registry completeness, all three locales, density/overflow assertions, clean Linux screenshot comparisons |
| CI visual lane and repository verifier | workflow syntax, fixed image digest, exact governed commands, artifact-on-failure/retention guard, temporary-scope removal, local CI verifier tests |
| Shared UI/catalog/contract/schema boundary | full repository/backend/frontend/runtime/non-visual/visual/security/migration/recovery and cumulative Level 3 checks |

## Validation plan

### Level 1 repair checks

After each batch:

- format/lint/type checks for changed files;
- directly affected Python/frontend unit tests;
- affected `en`/`zh`/`zh-TW` browser cases;
- relevant exact visual subset in the fixed renderer;
- targeted security/permission/manifest checks; and
- `git diff --check`.

Failures with one root cause are repaired together. No more than five genuine
repair rounds are allowed before applying the controller blocker rules.

### Stage 1 technical prototype gate

- complete prototype state-machine/component tests;
- exact no-production-transport/no-optimistic-success assertions;
- keyboard, focus, accessible name/status, reduced motion and axe;
- direct catalog coverage and mixed-language DOM scans;
- three-language 1440 prototype screenshots and original-resolution review;
- manifest/verifier tests with the real state still
  `PENDING_PRODUCT_OWNER`; and
- evidence that no backend/API/schema/business route changed.

### R1-06 Level 2 Task Gate

- every completed R1-06 module test;
- all affected My Work, shared UI, localization, P0 registry and visual tests;
- if activated, the complete reset/undo API/permission/runtime/migration suite;
- exact current requirement trace and `changed-files → affected-tests` audit;
- consequence/recovery and ineligible-action review;
- Task Diff Review, secrets/prohibited-pattern/TODO/stub/fake-success scan; and
- approval truth review separating technical evidence from business approval.

### Triggered and cumulative Level 3

Run the complete `implementation/QUALITY_GATE.md` Level 3 and
`release-gate` Skill requirements for:

- any Stage 2 public API/schema/permission/shared-UI change; and
- the mandatory R1 shared Shell/design/i18n exit boundary in all cases.

This includes full repository verification, complete backend/frontend suites,
controlled Frappe runtime and migrations, public contract agreement, complete
non-visual E2E, complete trilingual visual matrix in the fixed Linux renderer,
security and dependency scans, migration/rollback/recovery, traceability,
evidence integrity and independent code/domain/permission/security/UX/i18n/
visual review. Exact commands, counts, run/job/artifact IDs and hashes must be
recorded.

## Class-B and external gates

- The low-risk production duration and final prototype state/copy set require
  actual Product Owner approval.
- No business bulk-status action, eligibility policy or audit-recovery rule is
  approved. Full `UX-026` bulk acceptance remains a future domain-specific
  task.
- `DR-REC-001` still controls R1-07 only.
- Phase 3 business UAT and representative sanitized-data provenance remain
  externally unsigned and cannot be synthesized here.

These facts hold only their dependent behavior. Stage 1 technical prototype
work, Stage 3 visual governance and all safe verification continue.

## Migration, rollback and recovery

- Stage 0 is documentation-only and reverts as one checkpoint.
- Stage 1 prototype files and pending manifest are removable without retained
  business data; no production command exists.
- Stage 2, if approved, uses additive schema and append-only command/audit
  history. Before retained history, a disposable environment can return to the
  previous checkpoint. After retained history exists, disable only the exact
  reset/undo routes, preserve preference and audit rows, and deploy a reviewed
  forward correction; never delete history.
- Stage 3 adds tests, snapshots and CI governance. Rollback restores the prior
  CI command and removes only the exact new R1-06 baselines; historical
  accepted images remain untouched.
- Every stage updates the durable controller files, commits and pushes a
  recoverable checkpoint before automatic transition.
