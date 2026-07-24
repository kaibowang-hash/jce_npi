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

The Execution Pack means the repository's actual `GOAL.md`, contracts, docs,
design rules, specifications, implementation records, prompts, localization
material, and Skills; this controller coordinates that Pack and never replaces
it with a second product specification. Accepted ADRs govern after the Pack,
the DOCX is a completeness cross-check, and only reversible implementation
details may be selected without a business decision. A material conflict is
recorded as a Decision Request and never resolved by silently overwriting the
Pack.

## Permanent product and ownership boundaries

- NPI One is an independent engineering-project, NPI, and Tooling collaboration
  platform with its own Frappe Site/database and a React + TypeScript normal-user
  SPA. Desk remains an administration, audit, configuration, and support tool.
- The SPA follows the approved Siemens iX Classic Light / classic industrial
  engineering direction through company-owned tokens: one restrained dark-teal
  primary, predominantly neutral colors, square 0–2 px geometry, flat borders,
  dense trees/tables/split workspaces, stable toolbars and inspectors. Colorful
  card walls, gradients, glass effects, strong shadows, decorative consumer
  dashboards, and Siemens restricted brand assets are prohibited.
- English is the only source-copy language. All normal-user copy uses the local
  Frappe-compatible translation adapter/catalog and has complete direct `zh`
  and `zh-TW` coverage. Except for approved terminology, abbreviations, codes,
  units, formal names, filenames, and business data, mixed-language UI is a
  release blocker.
- Tooling Requirement, Tooling Master, Tooling Revision, Tooling Set, Insert,
  Cavity, and Trial are separate domain concepts. They must not be collapsed
  into a convenience record or lifecycle; Trial rounds bind exact Tooling,
  product, material, parameter, sample, cavity, defect, and evidence versions.
- NPI One owns development process, engineering baselines, stage gates,
  Tooling development, Trial collaboration, NPI readiness, and major
  engineering change. ERPNext owns formal customer/supplier/item master data,
  MBOM, purchasing, inventory, production, finance/cost, formal quality,
  production Tooling assets/maintenance, and production execution. A shared
  field has exactly one declared master; no direct database write or dual
  master is permitted.

## ERPNext reconciliation gate

Before implementing formal behavior that overlaps an existing ERPNext
customization, inspect the supplied custom apps, DocTypes/fields, workflows,
scripts, hooks/APIs, reports/prints, roles/permissions, numbering, lifecycle,
Tooling/quality/change/file customizations, and sanitized runtime evidence.
When complete, record the overlap/conflict matrix, object and field ownership,
numbering and lifecycle authority, reuse/extend/replace/interface decisions,
migration impact, and interface mapping. When incomplete, use the single
`REQUIRED_INPUTS.md`, pause only fact-dependent production mapping, and continue
contracts, explicit mocks, tests, documentation, and sandbox-ready adapters.

NPI One and ERPNext are not currently interconnected. Production ERPNext must
not be contacted, and no readiness work may be represented as a successful ERP
execution. Until reconciliation facts and separate activation approval exist,
the NPI One side is limited to Integration Readiness, explicit Mock behavior,
contracts, fault/retry evidence, and Sandbox-ready preparation.

## Continuous loop

Derive the next task by scanning `PHASE_STATUS.yaml` in phase order for the
first status other than `PASS`. A non-`PASS` phase remains the first incomplete
phase even when its Gate explicitly permits independent later work. Later-phase
work may start only when that phase's committed Gate names an exact Pack-approved
continuation state and explicitly authorizes the transition; the pending item
must remain visible and must not be relabelled `PASS`. Without that evidence,
the next task stays in the first incomplete phase.

For the first safely executable atomic task under that rule: use committed
requirement anchors and traceability as the index, read its related Pack
requirements and applicable skills, map requirements to implementation and
tests, implement one complete vertical slice, run the validation level defined
below, review the diff and traceability, repair failures up to five genuine
rounds, update evidence and controller state, commit the applicable checkpoint,
push this non-main branch and continue. A gate must never pass through skipped
checks, weakened criteria, fake data or fake success.

Every Phase loop covers static/type/lint checks; unit, API, integration and
permission tests; frontend/component/E2E tests; localization and mixed-language
scans; token, accessibility and visual regression review; security,
migration/rollback, health and recovery checks; Git diff review; requirement
traceability; evidence/status/risk/decision/blocker updates; and the complete
Quality Gate. Failures receive up to five genuine repair rounds. Tests,
thresholds, requirements, and evidence must never be deleted, skipped, weakened,
hard-coded, or falsified to manufacture PASS. A checkpoint is pushed before
automatic transition to the next Phase.

## Context and validation levels

Validation is cumulative across delivery boundaries: narrower checks optimize
the repair loop but never remove tests, reduce coverage, lower PASS criteria,
or replace a later Phase/PR/release gate.

### Level 1 — Incremental Check

Use for one small fix, local refactor, or test correction inside an active
atomic task. Derive and record a `changed-files → affected-tests` mapping, then
run only changed-file formatting/lint/type checks, directly related
unit/component tests, affected page/language/visual cases, necessary targeted
security or permission tests, and `git diff --check`. Shared components or
catalog edits require the affected page matrix, not automatically the complete
visual matrix.

### Level 2 — Task Gate

Use when an atomic task is complete. Run the current module's complete tests;
all affected API, permission, integration, E2E, i18n, and visual checks; current
Requirement ID traceability; the complete Task Diff Review; and every current
task acceptance criterion. Preserve exact commands and results as task
evidence. Level 2 does not declare a Phase or release complete.

### Level 3 — Full Release Gate

Use only at Phase completion, PR merge readiness, production release, changes
to public architecture/contracts/Schema/authentication/permission models,
changes to the shared design system/translation framework/core infrastructure,
or changes with multi-domain impact that cannot be bounded reliably. Run the
whole-repository type/lint/test suite; all API, permission, integration and E2E
checks; the complete English/`zh`/`zh-TW` matrix; the complete visual regression
matrix; security, migration, rollback, recovery; complete requirement
traceability; and the `release-gate` Skill. Save complete reproducible evidence.
If impact analysis is unreliable, escalate to Level 3 rather than guessing.

Failures sharing one root cause may be repaired together in one repair round.
After a related batch, rerun affected checks first; do not restart a complete
Gate after every individual failure. Run the applicable Task, Phase, PR, or
release Gate only after the batch is green. An Incremental Check can never be
used to bypass the complete Phase-level Gate.

Only a Hard Blocker defined by the governing instruction may stop the whole
loop. Missing production ERPNext material does not block contracts, mock and
sandbox-ready adapters, tests, UI or documentation. Missing reconciliation
facts pause only formal logic that depends on those facts.

The exhaustive Hard Blockers are: a required one-time Codespace create/rebuild
click; required GitHub browser authorization; required production secret or
production-system permission; irreversible production-data action; mutually
unsatisfiable highest-priority Pack rules; a required change to approved
architecture, industrial UI, language strategy, or data ownership; missing core
business facts on which *all* remaining work depends; a necessary Gate still
failing after five complete repair rounds; or a concrete license/security risk.
Stopping records one cause, completed scope, and the single user action needed.

Final completion requires a reproducible build and deployment, type and lint
checks, unit/API/permission/integration/E2E/visual tests, complete trilingual
coverage with zero unapproved mixing, security and migration/rollback checks,
health/backup/restore instructions, requirement-to-code/test evidence, no
accepted-path TODO/stub/placeholder/fake data, no unrecorded deviation, UAT
paths and truthful unsigned UAT status, and a passing release gate. The only
terminal controller states are `IMPLEMENTATION_COMPLETE` or `BLOCKED_EXTERNAL`.

## Durable recovery protocol

1. On a new session or Phase switch, read `AGENTS.md`, `GOAL.md`,
   `PHASE_STATUS.yaml`, `QUALITY_GATE.md`, the
   traceability/blocker/decision/risk/deviation logs, the current phase gate and
   phase specification, `NEXT_ACTION.md`, `LAST_RUN.md`, accepted ADRs and
   applicable skills.
2. Confirm the branch is `codex/npi-v1.2-implementation`; do not develop on
   `main`. Inspect Git status and preserve unrelated user changes.
3. Resume the first incomplete atomic task recorded in `NEXT_ACTION.md`; do not
   repeat work already evidenced by a passing checkpoint.
4. Before interruption, update status, next action, last run, traceability and
   evidence, then commit and push a complete recoverable checkpoint when the
   environment permits it.

At the start of an atomic task, read only its task record, indexed requirement
anchor/traceability rows, related domain specifications, contracts/ADRs, and
applicable Skills. Within that task, use the committed context and evidence;
do not repeatedly reread the full DOCX, `GOAL.md`, all Pack files, or unrelated
domains for small fixes. Expand reading only for a material ambiguity, contract
conflict, cross-domain impact, or insufficient anchor. DOCX is a completeness
cross-check, not a source to re-extract in every repair loop.

If context or execution may end, perform step 4 before any further feature
work. On resumption, trust committed evidence, start from the recorded first
incomplete atomic task, and never repeat already passing implementation.

Cloud-host checks and Codespaces checks are separate evidence lanes. Missing
Docker, denied registry access, or another Cloud-host limitation never revokes,
overwrites, or re-runs a valid committed Codespaces Gate. A task whose
acceptance requires Docker, a rebuilt Codespace, or local Frappe runtime is
recorded as environment-specific external validation; Cloud may continue only
documentation, static analysis, or other work whose acceptance it can execute
and report honestly. A toolchain change that requires fresh-target proof stays
pending until that proof is produced in Codespaces.

## Current checkpoint

- First incomplete phase: `3 — React App Shell Siemens UI and i18n Foundation`,
  status `TECHNICAL_PASS_PENDING_UAT`; it is not an unqualified `PASS`.
- Pending Phase 3 task: external business UAT and provenance-backed sanitized
  data for `FR-UX-031`. It requires the named business reviewers and cannot be
  signed or represented as complete by Codex.
- Exact continuation authority: `implementation/phase-3-gate.md` records a
  release-gate technical `PASS`, preserves
  `TECHNICAL_PASS_PENDING_UAT`, states that its external items do not block
  NPI-owned domain work, and explicitly activates Phase 4. This is the narrow
  Pack-approved state that permits independent later work; it does not turn
  Phase 3 into `PASS`.
- Safely executable task after the latest Full Release Gate: Phase 4 `P4-04`, subject
  to `NEXT_ACTION.md`. Phase 3 UAT remains the earlier incomplete external
  item.
- State at 2026-07-24T05:34:22Z: `IN_PROGRESS`. Phase 1.1 remains supported by
  the committed fresh-Codespaces evidence in `phase-1.1-gate.md`; this Cloud
  host's missing Docker and registry-tunnel 403 neither revalidate nor revoke
  that evidence.
- Latest result: bounded `P4-03` passed its triggered Level 3 Full Release
  Gate. It delivers independent versioned Gate Templates, exact Project
  Template bindings, frozen Project requirement assignments, append-only exact
  WBS/private File Revision evidence, live scanner-state truth, URL-free BFF
  metadata, and a trilingual live Gate evidence workspace. Authorization
  precedes protected-object validation, and historical exact template versions
  remain readable after their root is disabled while new bindings fail closed.
- Final cumulative evidence includes the 276-Python/237-frontend aggregate
  before the final two-file authorization-order repair, 20 directly affected
  tests after it, two successful Site migrations, the complete P4-01/P4-02/
  P4-03 real runtime, 153 non-visual browser cases, forced and clean 159-case
  exact visual matrices, original-resolution trilingual reviews, Task
  Diff/trace, security, and independent release review. The canonical catalogs
  contain 1274 direct entries per Chinese locale.
- FR-SG-001, FR-SG-002, FR-SG-004, and FR-CO-006 remain technically verified
  foundations. Production Gate condition/skip content, P0 normal-pass policy,
  review/waiver/reopen/invalidation authority, future evidence resolvers,
  external-user notification/email/print delivery, and production scanner/DMS
  behavior are not delivered. P4-04 owns only the review/decision/snapshot/
  reopen boundary under safe-default-denied rules; later applicable Level 3
  boundaries remain mandatory.
- Phase 3 is truthfully retained as `TECHNICAL_PASS_PENDING_UAT`: named business
  sign-off and provenance-backed sanitized sample review remain open but are not
  a global blocker. Phase 4 is active under automatic-transition authority.
  Production ERPNext remains prohibited, and ambiguous production rules remain
  scoped holds rather than invented defaults.

See `NEXT_ACTION.md` for the single recovery action and `LAST_RUN.md` for exact
evidence.
