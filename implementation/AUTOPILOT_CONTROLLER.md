# V1.2 Autopilot Controller

Updated: `2026-08-07T22:10:17Z`

## Authority and operating mode

The repository is in V1.2 continuous-delivery mode on
`codex/npi-v1.2-implementation`. After a Phase Gate is `PASS`, execution moves
to the next phase without waiting for another prompt. Product, domain,
architecture, industrial-UX, localization, security, ownership and release
rules remain mandatory. Production ERPNext must not be contacted.

The execution authority order is the latest compatible user instruction,
`AGENTS.md`, the authoritative V1.2 DOCX together with the accepted additive
reconciliation, the V1.2 Execution Pack, contracts/accepted ADRs, applicable
Skills, and reversible implementation choices. The current DOCX/Pack
crosswalk is machine-readable in
`implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv`; historical differences
remain in `DOCX_PACK_DEVIATIONS.md`. A material conflict pauses only affected
work unless it blocks everything.

The user's 2026-08-06 standing recovery authority permits Autopilot to resolve
this and later technical Hard Blockers without requesting another prompt. It
does not broaden product scope or weaken any invariant. For an opaque runtime
failure, Autopilot must execute serial bounded cycles: activate only an
existing response-neutral diagnostic for the first affected request, pass
affected/full ordinary CI, run one diagnostic Site, repair only the uniquely
proved root, close diagnostics, pass affected/full ordinary CI and run one
final unchanged Gate. If that Gate exposes a new opaque downstream root, a
new identical cycle may begin automatically while all historical counters and
evidence remain immutable. Autopilot still pauses for a Class-B business
decision, Class-C/high-risk or destructive approval, or an external manual
action that only the user can perform.

The Execution Pack means the repository's actual `GOAL.md`, contracts, docs,
design rules, specifications, implementation records, prompts, localization
material, and Skills; this controller coordinates that Pack and never replaces
it with a second product specification. The 2026-07-25 reconciliation addendum
and the append-only 2026-07-27 `FR-UX-043` correction amend the Pack
additively: all 229 DOCX IDs, 39 Pack-only normalized IDs and 14 clarification
IDs remain visible in the current 282-row trace. The historical 281-row R1-01
checkpoint remains unchanged. Only reversible implementation details may be
selected without a business decision. A material conflict is recorded as a
Decision Request and never resolved by silently overwriting an authority.

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
work may start only when that phase's committed Gate names an exact
trace/addendum-approved continuation state and explicitly authorizes the
transition; the pending item must remain visible and must not be relabelled
`PASS`. Without that evidence, the next task stays in the first incomplete
phase.

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

Repair-round accounting is product-root based:

- Runner tools, package presentation, container/Bench/Site bootstrap, App
  registry, migration invocation, verifier metadata, and clearly synthetic
  fixture-precondition failures are environment remediation. They remain
  fail-closed and require fresh evidence, but do not consume a product-root
  repair round.
- A behavior-neutral diagnostic checkpoint that emits only closed stage codes,
  validated exception types and exact trace IDs is
  `IN_PROGRESS_DIAGNOSTIC`. It does not consume a product-root repair round and
  is never a Gate `PASS`.
- A product-root repair round begins only after the pinned environment,
  guarded disposable Site, required App installations and migrations, and
  current-task fixture preconditions have passed and evidence uniquely proves
  one implementation root inside the active task.
- A disproved and fully forward-reverted candidate is retained as evidence but
  is not represented as a completed product-root repair. A proven repair that
  advances the same unchanged Gate to a new downstream root counts once.

Under standing automatic-delivery authority, safe diagnostic narrowing and a
uniquely proven in-scope repair continue inside the active task and remaining
product-root budget. Exhausting a per-dispatch diagnostic allowance is an
execution-authority hold only when the governing user instruction explicitly
made that allowance terminal; it is not by itself a product Hard Blocker.
Requirement, API, permission, Schema, ownership, lock, version, audit,
idempotency, transaction-order and PASS-criterion changes remain outside this
automatic repair authority.

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
failing after five complete product-root repair rounds; or a concrete
license/security risk. An environment remediation or
`IN_PROGRESS_DIAGNOSTIC` state cannot be relabelled as `PASS`, but neither is a
Hard Blocker while a safe in-scope action remains under current authority.
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
conflict, cross-domain impact, or insufficient anchor. The checked-in 229-row
DOCX extraction and coverage matrix are the normal requirement index; do not
re-read or re-extract the complete DOCX in every repair loop.

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

- Active execution goal: `implementation/ACTIVE_EXECUTION_GOAL.md`.
- Branch: `codex/npi-v1.2-implementation`.
- Phase 5 remains `IN_PROGRESS`; P5-00, P5-01, P5-02 and P5-03 are `PASS`.
- P5-03 product checkpoint
  `302b1e90d3561b57d6815dca186e5c33bcb8e693` passed complete normal CI
  `30990594281`, final unchanged controlled-Site workflow `30991177478` and
  its Level 2 Task Gate. Complete evidence:
  `implementation/evidence/phase-5/p5-03-validation.md`.
- P5-04 is the only active atomic task. Its domain/metadata,
  repository/BFF/OpenAPI and frontend stages passed their recorded checks.
  Policy publication repair `d21d21a` passed ordinary CI `31020190868`; final
  controlled workflow `31020886002` advanced to the non-unique
  `P504_RUNTIME_CREATE / HttpStatusError /
  trace-f92a1e065fe35759b261601244cca7d4` boundary.
- The user authorized one bounded create-stage diagnostic/repair sequence on
  2026-08-06. Diagnostic checkpoint `008e6ed` passed complete ordinary CI
  `31069567886`; the sole diagnostic workflow `31069924517` returned only
  `P504_CREATE_DOMAIN_BUILD / RequestValidationFailed /
  trace-79bcd3a2408c5f71bb8c0cad8bd9db21`.
- Cross-validation uniquely proves a synthetic fixture precondition root: its
  policy namespace and EBOM key did not satisfy the frozen
  `syntheticNamespace + "-"` relation. The bounded fixture-only repair shares
  one `synthetic_ebom` namespace, preserves the domain rule and has closed
  diagnostic activation. Complete EBOM tests pass `63/63`; repair checkpoint
  `158ef02` passed complete Python `959/959` and ordinary CI `31070341154`.
- Final unchanged workflow `31070732986` advanced beyond the former domain
  failure, then returned only `P504_RUNTIME_CREATE / HttpStatusError /
  trace-462662eec74c5c4f9e3e5a07258f1a7b`. This tuple remains non-unique across
  the remaining create transaction/response stages. Companion repository job
  `92517955490` and visual job `92517955368` passed. The sole diagnostic Site,
  one fixture repair and final Gate are exhausted historical allowances.
- Blocker recovery checkpoint `40c8956` passed exact-SHA ordinary CI
  `31071143272`; repository job `92519171196`, complete E2E/history secret
  scan and visual job `92519171311` passed, while the controlled job
  `92519171741` remained correctly skipped.
- Controller-reconciliation checkpoint `c7edac8` passed exact-SHA ordinary CI
  `31071703360`; the controlled job remained correctly skipped.
- The user explicitly authorized a new separate remaining-create-stage
  sequence on `c7edac8`: reactivate only the existing first-create
  response-neutral diagnostic, require affected/full ordinary CI, run at most
  one diagnostic Site, repair only one uniquely proved in-scope root, rerun
  affected/full ordinary CI and reserve one final unchanged Gate. New counters
  are diagnostic `0/1`, uniquely proved repair `0/1` and final Gate `0/1`.
- Diagnostic checkpoint `40d2d47` passed complete exact-SHA ordinary CI
  `31073500593`. The sole diagnostic workflow `31073915463` then emitted only
  `P504_CREATE_REVISION_INSERT / ValidationError /
  trace-9b23575185625a1998ac184bfefaa272`; companion repository and visual jobs
  and disposable cleanup passed.
- `require_exact_parent()` returns expected plus explicit extra fields, not
  its filter keys. The revision controller passed that row to
  `ebom_policy_value()` without selecting required `policy_global_id` and
  `policy_version`, uniquely proving the observed validation root. The bounded
  repair selects only those two existing fields and closes diagnostics.
- Repair checkpoint `f4aba87` passed complete exact-SHA ordinary CI
  `31075372272`: repository `92532129789` and visual `92532130528` passed;
  controlled job `92532130580` correctly skipped.
- The sole final unchanged workflow `31075730002` retained exact SHA
  `f4aba87`. Repository `92533233067`, visual `92533232990`, predecessor
  runtime, migrations and disposable cleanup passed, but controlled job
  `92533233034` returned only `P504_RUNTIME_CREATE / HttpStatusError /
  trace-6fa26f47b241558db7fdafa0b9c1a46e`.
- Because diagnostic activation was correctly closed, the final tuple cannot
  distinguish recurrence of the revision-insert validation from a later
  create transaction/response failure. The new diagnostic `1/1`, uniquely
  proved repair `1/1` and final unchanged Gate `1/1` are exhausted. P5-04 is
  `BLOCKED_EXTERNAL`; another Site dispatch or repair requires new explicit
  bounded authority and may not guess a root.
- The user then requested that the problem be fixed, resuming the same Goal on
  exact base `16ed463`. One new independent post-revision-create sequence is
  active. Diagnostic checkpoint `1400a8b` passed complete ordinary CI
  `31079745399`; the sole diagnostic Site `31080379082` uniquely emitted
  `P504_CREATE_LIFECYCLE_INSERT / ValidationError /
  trace-16676d79fc405e76805261a931550f32`, while repository and visual passed.
  The preceding line controller already passed the same exact revision,
  tenant, Project and snapshot-hash predicate. The lifecycle controller then
  supplied its canonical string ID to the UUID-only domain boundary, uniquely
  proving the one authorized repair. Counters are diagnostic `1/1`, repair
  `1/1`, final unchanged Gate `1/1`; diagnostic activation is closed. Repair
  checkpoint `6a4ba7c` passed complete ordinary CI `31081784934`. The sole
  final workflow `31082337133` retained that exact SHA, passed repository and
  visual companions, predecessor runtime, setup, migrations and cleanup, then
  returned only
  `P504_RUNTIME_CREATE / HttpStatusError /
  trace-ef925ea360245bd6b58daf326b910afe`. The aggregate final tuple cannot
  distinguish lifecycle recurrence from a later create stage. The standing
  recovery authority therefore opens a new bounded post-lifecycle cycle
  automatically: only the first-create diagnostic is active, affected/full
  ordinary CI is required before one diagnostic Site, and only its uniquely
  proved root may be repaired before diagnostics are closed and the unchanged
  Gate is rerun.
- Diagnostic checkpoint `233b23f` passed ordinary CI `31084462702`. The sole
  diagnostic Site `31085013974` retained that SHA and uniquely returned
  `P504_CREATE_AUDIT_APPEND / PermissionError /
  trace-ee528c1626eb59c4ba40f1ffea1b86ce`; repository and visual companions,
  fixed setup and cleanup passed. Earlier create substages passed. The audit
  DocType requires `npi_audit_append`, while the authorized EBOM command and
  lifecycle scopes omit that flag even though they call the inherited direct
  audit append. The current repair adds only that internal flag to those two
  existing scopes, restores prior values and closes diagnostics. It changes
  no role, DocPerm, public contract, transaction order or audit content.
  Local controller/runtime `26/26`, complete EBOM `65/65`, tracked Python
  `955/955` and governance checks pass with diagnostics closed. The next
  boundary is complete exact-SHA ordinary CI, followed by the one final
  unchanged Gate.
- Repair checkpoint `1fda74a` passed exact-SHA ordinary CI `31086008989`:
  repository `92565500998` and visual `92565500984` passed, and controlled
  job `92565501739` correctly skipped. Final unchanged workflow `31086562000`
  retained that exact SHA. Repository `92567276324`, visual `92567276329`,
  fixed Bench/Site, migrations, predecessor runtime and cleanup passed;
  controlled job `92567276189` advanced through repaired create and emitted
  only `P504_RUNTIME_SUBMIT_REVIEW / HttpStatusError /
  trace-1494387c76f6549899ce007d429ba163`.
- The audit repair therefore worked; the new aggregate is a distinct
  downstream submit-review boundary. Standing authority opens the next
  serial cycle without user intervention. Only the submit-review request may
  activate the separate response-neutral transition diagnostic. It records
  at most one allowlisted stage/type/trace tuple and changes no response,
  permission, Schema, ownership, transaction, idempotency, audit or PASS
  invariant. Affected/full ordinary CI must pass before its one diagnostic
  Site; only a uniquely proved root may be repaired; diagnostics must close
  before one final unchanged Gate.
- Diagnostic checkpoint `f47f4ef` passed exact-SHA ordinary CI `31087964089`;
  repository `92571837026` and visual `92571836950` passed and controlled
  runtime correctly skipped. The one diagnostic Site `31088548041` retained
  that SHA; repository `92573744222`, visual `92573744180`, setup, migrations,
  predecessor runtime and cleanup passed. Controlled job `92573744244`
  emitted only `P504_TRANSITION_LIFECYCLE_PROJECTION_SAVE / ValidationError /
  trace-15866486cf445bb0bac3dc35120d6318` after receipt/event insertion.
- The controller normalizes `last_event_global_id` to canonical text and
  validates the exact event, then handed that text to a UUID-only domain
  field. Convert only the already-validated non-null event ID to `UUID`, keep
  every state/version/parent predicate, close diagnostic activation and run
  affected/full ordinary CI before the final unchanged Gate. Local
  controller/runtime `29/29` and complete EBOM `69/69` pass.
- P5-05 and Phase 6 remain inactive.
- P5-04 is `IN_PROGRESS_VALIDATION`, never yet a Gate PASS. Production numbering,
  reviewer/approver authority, signatures, production baseline contents and
  authority, production dependency matrix, EBOM numbering/line/quantity/UOM/
  alternate/effectivity/release rules, external identity/retrieval,
  scanner/viewer providers, CAD/PDM and production ERPNext remain scoped
  fail-closed holds and are not represented as implemented.
- Current trace remains 282 unique IDs:
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.
- Existing uncommitted workspace changes remain user-owned and must not be
  staged with an Auto Pilot checkpoint.

## Historical checkpoint through P5-01 recovery

- Active execution goal: `implementation/ACTIVE_EXECUTION_GOAL.md`.
- Current synchronized recovery checkpoint:
  `ee8730133e8cdd30fc7bff158ab80a252ed14249`.
- Completed bridge tasks: `R1-01 — DOCX Pack reconciliation addendum and
  machine trace`, `R1-02 — LaunchFlow display brand adapter and exact supplied
  assets` (`PASS — LEVEL 2`), `R1-03 — App Shell collapsed navigation command
  and contextual quick-create`
  (`PASS — LEVEL 3 PUBLIC SESSION-CONTRACT TASK GATE`), and
  `R1-04 — Shared grid sizing personalization views and export foundation`
  (`PASS — LEVEL 3 GRID PERSONALIZATION/SCHEMA TASK GATE`), and
  `R1-05 — Resizable panes, field attachment, and icon action primitives`
  (`PASS — STAGES 1–3`), and
  `R1-06 — Controlled undo prototype gate and 1440 visual governance`
  (`PASS — LEVEL 2 TASK GATE; STAGE 2 PRODUCT APPROVAL HOLD RETAINED`).
  R1 is an inserted bridge, not a replacement controller Phase.
- Current controller task:
  `P5-01 — Document and design revision`
  (`IN_PROGRESS — RESUME AUDIT PASS; FRONTEND/RUNTIME READY`).
- The R1 bridge and its cumulative shared Shell/design/i18n Level 3 exit Gate
  are `PASS`. The bounded P5-01 backend/domain/contract checkpoint is retained
  at `930b5a2`; its current-boundary resume audit passed without product
  correction, and P5-01 is not `PASS`.
- Current requirement inventory: 282 unique trace rows — 173
  `PACK_CANONICAL`, 95 `DOCX_RECONCILED`, and 14 `ADDENDUM_DIRECT`.
- Current reconciliation authorities:
  `docs/V1_2_RECONCILIATION_ADDENDUM.md`,
  `implementation/V1_2_DOCX_REQUIREMENTS.csv`,
  `implementation/V1_2_DOCX_PACK_COVERAGE_MATRIX.csv`,
  `docs/reference/TOOLING_LIST_FIELD_MAPPING.csv`, and
  `implementation/V1_2_RECONCILIATION_DECISIONS.md`.
- Brand authority: only `docs/Brand Asset/Brand Asset Instruction.csv`, the
  exact five LaunchFlow SVGs and subsequently supplied `Core.png` beside it.
  R1-02 completed the five-SVG LaunchFlow display boundary; `Core.png` remains
  allocated to FR-BR-002/Phase 8/M7-09. No alternative mark, inferred palette,
  redrawn asset or substitute is authorized. Stable technical codes `NPI_ONE`,
  `ERPNEXT` and `/api/npi/v1` remain unchanged.
- First incomplete Phase remains Phase 3
  `TECHNICAL_PASS_PENDING_UAT`; the named business UAT is external and does
  not invalidate its technical evidence or block safe later work.
- Latest completed product Phase remains Phase 4 `PASS`; its historical Gate
  evidence is immutable and is not recalculated against the amended trace.
- Phase 5 remains `IN_PROGRESS`; P5-00 remains a historical `PASS`, P5-01 is
  resumed at its checkpoint, and P5-02 through P5-05 remain inactive.
- R1-01 changed specifications, trace/index metadata, planning and safe
  inspection tooling only. R1-02 changed the shared frontend Shell,
  Frappe-compatible catalogs and display-brand build guard. R1-03 added only
  the fixed authenticated navigation-preference bootstrap/PUT contract and
  shared Shell command/quick-create foundations. R1-04 added the fixed
  authenticated My Work grid-preference resource, shared DenseGrid behavior
  and three additive personal/published-view DocTypes. Its final audit repairs
  keep exact persisted pixel widths, serialize version-confirmed preference
  writes, close the seven-view schema and enforce Unicode code-point search
  limits while keeping publisher, export and bulk authority fail closed.
- R1-05 Stage 1 added one fixed actor-bound My Work inspector preference,
  visible bounded pointer/keyboard resize, collapse/focus recovery and
  responsive presentation-only stacking. Its final evidence records the
  terminal canonical full Gate at 747 Python tests, 577 frontend unit tests
  and 2,671 direct trilingual sources, plus 256 non-visual browser cases, 210
  clean exact visual cases, all 18 controlled route disable/recovery
  contracts, zero residual inspector `DefaultValue` rows and independent
  audits with zero findings.
- R1-05 Stage 2 added reusable field and attachment truth primitives, a
  fail-closed injected transport state machine, visible local-file identity
  through asynchronous/failure states, URL-free exact registered revision
  facts, local-only Trial integration and read-only Gate evidence integration.
  Its Level 2 evidence records 614 frontend unit tests, 2,735 complete direct
  trilingual sources, focused browser `12/12`, affected page `20/20`, Gate
  visual `23/23`, Trial visual `24/24`, zero npm vulnerabilities and an
  independent post-repair PASS.
- R1-05 Stage 3 added a closed local icon-action policy and fail-closed iX
  mapping while preserving visible labels for primary, high-risk and
  ambiguous actions. Its Level 2 evidence records `620/620` frontend unit,
  `754/754` Python, `265/265` non-visual browser and `6/6` affected
  digest-pinned Linux visual cases, complete direct trilingual coverage and
  both action-range and complete-branch secret scans.
- R1-06 Stage 1 passed only as technical no-mutation prototype/governance
  evidence. Its unsigned Product Owner approval keeps the Stage 2 backend
  command and full business claim fail-closed.
- R1-06 Stage 3 and its Level 2 Task Gate passed at the fixed-Linux product
  checkpoint `0b3a7b28bb447edbc165daa95a3e9963f255d832`, followed by the pushed
  evidence/trace/controller checkpoint
  `5fae1784e376c08cd4466c1b38592eb9a7ec513e`. The current exact evidence is
  `762/762` Python, `634/634` frontend unit, `279/279` non-visual browser,
  `24/24` fixed-Linux affected visuals and `2,782` direct trilingual sources.
- `DR-REC-001` remains `PENDING_PRODUCT_OWNER`, so conditional R1-07 is
  skipped without being marked complete. The cumulative R1 shared
  Shell/design/i18n Level 3 exit Gate passed at CI `#72`; recovery checkpoint
  `c980571b27be66e16f2ac57409f0ef72a986e741` then passed CI `#73` with
  `764/764` Python, `634/634` frontend unit, `279/279` non-visual browser and
  `24/24` fixed-Linux visual checks. The exact P5-01 resume-audit checkpoint
  `ee8730133e8cdd30fc7bff158ab80a252ed14249` then passed CI `#74`, run
  `30549749537`, and is the current recovery point. Preserve the scoped holds
  and run only the unfinished P5-01 frontend/runtime slice next.

Resume only from `implementation/NEXT_ACTION.md`, the Phase 5 anchor and the
retained P5-01 checkpoint evidence. Reuse the passing Phase 4, P5-00 and R1
evidence where the current impact map proves the boundary unchanged; do not
repeat or rewrite it merely to restore context. See
`implementation/evidence/reconciliation/r1-shared-bridge-level-3-validation.md`,
`implementation/evidence/phase-5/p5-01-plan.md`,
`implementation/evidence/phase-5/p5-01-resume-audit.md` and
`implementation/LAST_RUN.md` for the exact latest result.

## 2026-08-06 P5-04 final PASS and automatic P5-05 transition

- Product repair `2c0734a4201ac5ee4b53eae913ce01172634da3f`
  passed exact-SHA ordinary CI `31089637022` and the single final unchanged
  controlled-Site Gate `31090154694` with every P5-04 diagnostic activation
  closed.
- The final Gate passed repository `92578962756`, controlled Site
  `92578962766`, fixed-Linux visual `92578962797`, both migrations, unchanged
  P5-01/02/03 runtime, complete EBOM lifecycle and bounded cleanup. Artifact
  `8963145655` records `result=PASS` and
  `scope=p5-01-through-p5-04` at exact SHA `2c0734a`.
- The lifecycle projection UUID repair changed only the already-canonical,
  exact-parent-validated hydration type boundary. No Requirement, API,
  permission, Schema, ownership, state, transaction, idempotency, audit or
  PASS criterion changed.
- Release-gate review concludes `PASS — LEVEL 2 P5-04`.
  `FR-DS-011` and `FR-DS-012` are `TECHNICAL_VERIFIED`; evidence is
  `implementation/evidence/phase-5/p5-04-validation.md`.
- Automatic-transition authority activates P5-05 for `FR-DS-013`. Its first
  action is the pure operation-specific Item/MBOM publish-request domain,
  closed contract and additive metadata described by
  `implementation/evidence/phase-5/p5-05-plan.md`.
- Mock is the only enabled Phase 5 mode and cannot report target identifiers
  or `succeeded`. Production ERPNext access, credentials, network dispatch,
  actual retry/replay/webhooks and reconciliation remain prohibited and
  deferred to Phase 8.

## 2026-08-06 P5-05 domain/contract/metadata checkpoint

- Product foundation `258277cc018a9e8b72cccb921b94e84b3dd0cb59`
  adds only the closed operation-specific domain, OpenAPI/ownership/event
  vocabulary, seven additive guarded DocTypes and complete direct trilingual
  catalog. Mock cannot dispatch, expose formal Item/MBOM identifiers or report
  execution success.
- Ordinary CI `31093873820` proved repository `92591063338`, complete E2E and
  both secret lanes PASS. Its visual job isolated exactly eighteen durable P0
  status-bar catalog fingerprint deltas; all other `44/62` cases passed.
- Artifact `8964668073` and original-resolution/exact-pixel review proved every
  delta was confined to `y=879..899`, with zero workspace changes and only the
  approved catalog fingerprint moving from `b4eead0d9711948` to
  `da1371bd0cacf5c2`.
- Evidence repair `a76f9c0cac313dabb80d0b31846345b5593c8d35`
  changes only those eighteen exact Linux baselines. Complete ordinary CI
  `31094889018` then passed repository `92594388442`, E2E, both secret lanes
  and fixed-Linux visual `92594388260` at `62/62`; controlled runtime correctly
  skipped.
- Checkpoint 1 is closed. Autopilot continues with repository, independent
  authority, actor-bound idempotency, atomic audit/persistence and BFF Mock
  create/read behavior. Production ERPNext, network dispatch, Outbox execution
  and Phase 8 retry/reconciliation remain inactive.

## 2026-08-06 P5-05 repository/API checkpoint

- Product checkpoint `0e3b13d87e4106be7a748db920f57ab43fda2d37`
  adds exact released-EBOM/published-policy resolution, independent requester
  authority, actor-bound idempotency, atomic request/node/mapping/result/audit/
  response persistence and operation-specific Mock list/create/detail BFF
  behavior. It creates no Outbox work, network request, formal target ID or
  `succeeded` state.
- Ordinary CI `31096833679` proved repository `92600762979`, complete E2E and
  both secret lanes PASS. Its visual job failed only the exact eighteen
  durable normal P0 catalog-fingerprint cases; all other `44/62` passed.
- Artifact `8965851155` and original RGB comparison proved every delta was
  confined to two bottom-status-bar boxes at `y=882..891`, with only
  `694..696` pixels per image and zero product-workspace pixels changed.
- Evidence repair `f3018eb94a54fa63cd87e87fb501835510765145`
  copies only those eighteen exact CI actuals to their matching tracked Linux
  baselines. No matrix, threshold, product code or PASS criterion changed.
- Complete unchanged ordinary CI `31097900948` then passed repository
  `92604192980` and fixed-Linux visual `92604192993`; controlled runtime
  correctly skipped. Evidence is
  `implementation/evidence/phase-5/p5-05-repository-api-checkpoint.md`.
- Checkpoint 2 and its Hard Blocker are closed. Autopilot continues with only
  the EBOM publish-request workspace, complete trilingual/accessibility/
  browser/visual evidence and ordinary CI. Controlled runtime, P5-05 Level 2
  and the Phase 5 Level 3 Gate remain inactive until checkpoint 3 passes.

## 2026-08-06 P5-05 publish-request workspace checkpoint

- Product checkpoint `358db2045e944d9d3bebb738245938977801028c`
  adds the closed live data source and dense Project EBOM publish-request
  workspace. It exposes exact released-input, policy, request, node, mapping
  and result truth; Mock remains no-contact and cannot report formal target
  identifiers or execution success.
- Ordinary CI `31100523170` proved the repository, complete E2E and both secret
  lanes PASS. Its visual artifact isolated eighteen P0 catalog-only deltas and
  three P5-04 single-primary-action regressions. Exact pixel proof found zero
  changed P0 workspace pixels.
- Repair `82d23595479c023d2dd625ff3d005e9b49c9a831` accepts only the eighteen
  reviewed P0 fingerprints, restores the context-dependent single primary
  action and additively governs three P5-05 language/viewport cases.
- CI `31103164950` then passed all pre-existing/repaired visuals `62/65` and
  failed only the three not-yet-created P5-05 Linux baselines. All three
  actuals passed original-resolution industrial UX and localization review and
  became the exact initial baselines at `4f4baf9`.
- Complete ordinary CI `31104305011` passed repository `92625383049`, complete
  non-visual E2E, both secret lanes and visual `92625383029` at `65/65`.
  Evidence is
  `implementation/evidence/phase-5/p5-05-frontend-checkpoint.md`.
- Checkpoint 3 and its bounded visual Hard Blocker are closed. Autopilot
  continues with the controlled disposable-Site P5-05 verifier, ordinary CI,
  one unchanged controlled Gate, P5-05 Level 2 and Phase 5 Level 3. No
  Requirement, API, permission, Schema, ownership, transaction, idempotency,
  audit or PASS criterion changed.

## 2026-08-07 P5-05 final PASS and automatic P5-06 transition

- Original controlled-runtime Hard Blocker is closed at exact product
  checkpoint `7624497acf19ca280d7331c41d4fc2eedb69e12e`. Ordinary CI
  `31134844746` passed repository `92731803737`, complete E2E/history secret
  scan and fixed-Linux visual `92731803668` at `65/65`; controlled runtime
  correctly skipped.
- Final unchanged controlled Gate `31135330539` passed repository
  `92733288503`, controlled disposable Site `92733288519` and visual
  `92733288492`. Artifact `8977753018` records
  `scope=p5-01-through-p5-05`; its GitHub SHA-256 is
  `bccec9800be67c9194c18508d3627839db4f7e67d0ece154b2fbe566cdb45e60`
  and extracted `result.txt` SHA-256 is
  `ce1e67fa1626b730be409281b5f0421bcea6817e7043364c19456f075491f17f`.
- GitHub Actions workflow `31115995065` failed before checkout while the
  official Actions component was in partial outage; its `Service Unavailable`
  action-download error was external and did not reopen product truth.
- The next ordinary run exposed newly published high-severity advisory
  `CVE-2026-59870` only through the transitive development path
  `stylelint -> cosmiconfig -> js-yaml`. Commit `7624497` updates the lock from
  compatible `js-yaml` `4.3.0` to patched `4.3.1`; both exact-SHA runs prove
  zero npm vulnerabilities without changing product behavior or thresholds.
- Release-gate review concludes `PASS — LEVEL 2 P5-05`.
  `FR-DS-013` is `TECHNICAL_VERIFIED_FOUNDATION`; production Item/MBOM
  execution remains owned by ERPNext and deferred to Phase 8. There is no
  active technical Hard Blocker.
- The reconciliation-amended Phase 5 requirement anchor includes planned P0
  print foundation `M4-06`. Phase 5 therefore remains `IN_PROGRESS`, and
  Autopilot activates P5-06 for `FR-PRN-001` and `FR-PRN-002`: only a generic
  server-side Print Format registry and immutable controlled-output snapshot
  foundation. The full CI at `7624497` is reusable release-readiness evidence,
  not a premature terminal Phase Gate.
- Exact production forms, signers, copy count and policy under `FR-PRN-003`
  remain held for P5-07 by `DR-REC-003` and `DR-REC-004`. P5-06 may not invent
  those business rules, install production defaults or contact ERPNext.

## 2026-08-07 P5-06 requirement and existing-capability audit

- Evidence-only checkpoint `ac890c0` passed the complete product repository
  verification and fixed-Linux visual `65/65`; its sole ordinary-CI failure
  was the history scanner classifying the public Git checkpoint stored at
  `PHASE_STATUS.yaml:554` as a generic API key. The bounded repair retains only
  that exact immutable commit/path/rule/line fingerprint in the existing
  strict reviewed set; no regex, path, rule, entropy, history scope or secret
  criterion is relaxed.
- The bounded audit for `FR-PRN-001/002` passes. NPI Core contains no existing
  print route, registry mapping, output snapshot or seeded template that could
  be relabelled as completion.
- Existing canonical JSON/SHA-256 baseline patterns, exact private local File
  validation, immutable audit, Project authorization, actor-bound
  idempotency, atomic receipt and independent route-switch conventions are
  reusable without moving ownership.
- Official source at the pinned Frappe commit provides native `Print Format`
  and server-side PDF generation. Its live-Document print path cannot be used
  to substitute current data after snapshot creation; P5-06 freezes source
  data and exact template content/hash first, renders once, and retains the
  same private output for audited reprint.
- No QR dependency exists in the pinned runtime, so no package or external
  service is authorized. The plan requires a bounded repository-owned
  deterministic SVG utility with fixed-vector tests and fail-closed behavior.
- Evidence and the complete scope/test/rollback map are frozen in
  `implementation/evidence/phase-5/p5-06-plan.md`. Autopilot proceeds with the
  pure domain, closed contract and additive guarded metadata checkpoint only.
  No live route, renderer, File write, UI action, fixture, Print Format or
  enabled mapping is part of that first checkpoint.

## 2026-08-07 P5-06 domain, contract and metadata checkpoint

- Product checkpoint `07111e3` adds the pure exact-mapping and immutable
  snapshot/output/access domain, six guarded additive DocTypes, closed
  capability/create/detail/content schemas, NPI-owned ownership vocabulary and
  direct English/`zh`/`zh-TW` coverage. It installs no route, renderer, File
  write, mapping, Print Format, fixture or production default.
- Local affected and complete regression passed: focused `20/20`, contract
  `85/85`, metadata `88/88`, localization `41/41`, complete Python
  `1,034/1,034`, catalog generation/i18n at `3,856` sources and V1.2/P0
  governance checks.
- Initial ordinary CI `31138842148` passed repository `92744201653` and all
  `47` non-P0 governed visual cases. Its only failure was the exact eighteen
  fixed P0 footer catalog fingerprints changing from `2ad33967abb8b251` to
  `8c614f1fb035060a`; artifact `8979072126` proved no component/layout/state
  change. The exact stable Linux actuals were synchronized byte-for-byte in
  isolated commit `68a79fd`; no threshold, assertion, matrix or PASS rule
  changed and no user Darwin evidence was touched.
- Clean exact-SHA ordinary CI `31139557282` passes repository `92746365839`,
  complete E2E and both secret lanes, plus visual `92746365786` at `65/65`;
  controlled job `92746366536` correctly skips. The visual artifact is
  `8979344607` with digest
  `sha256:3aa906402ec918ed7c1903b10d8e0e410aa867d39ba1f5fe71feb5d187c5b67e`.
- Checkpoint 1 is PASS. P5-06 remains active for the exact source/registry
  repository, deterministic verification SVG, frozen-template one-time render,
  private retained File/output, atomic idempotency/audit transaction and
  closed BFF behavior. Exact forms/signers/copy policy remain decision-held.

## 2026-08-07 P5-06 repository, retained render and API checkpoint

- Exact stable checkpoint `10963dd` adds the server-owned source/registry
  repository, deterministic verification SVG, frozen-template one-time PDF
  render, private local File/output retention, actor/Project-bound
  idempotency/audit transaction and closed capability/create/detail/content
  BFF behavior.
- Authorization precedes protected resolution. Missing, ambiguous, stale or
  drifted mappings fail closed; create/render/download never accept a raw
  DocType, template, source payload, controlled provenance or File URL from
  the browser. Replays and downloads reuse the same verified retained bytes
  without source resolution or rerendering.
- Focused P5-06 validation passed `56/56`; complete tracked Python passed
  `1,070/1,070`; compilation, reconciliation, P0 governance, i18n at `3,857`
  sources and exact diff/security scans passed.
- Complete exact-SHA ordinary CI `31144008180` passed repository
  `92759644660`, complete E2E and both secret lanes, plus visual
  `92759644740` at `65/65`; controlled job `92759645318` correctly skipped.
  Visual artifact `8980844734` has digest
  `sha256:f85a143df03444c3805561f3f9eafcd874b385ccc856d0d3ac7a2cc8918da262`.
- Evidence is
  `implementation/evidence/phase-5/p5-06-repository-api-checkpoint.md`.
  Checkpoint 2 is PASS. Autopilot continues with only the reusable dense SPA
  print affordance/status surface, direct English/`zh`/`zh-TW`, accessibility
  and affected browser/visual evidence. No production adapter, Print Format,
  enabled mapping, form, signer, copy policy, dependency, external service or
  ERPNext endpoint is active.

## 2026-08-07 P5-06 final PASS and Phase 5 Level 3 transition

- Frontend checkpoint `83ffafc` completes the strict controlled-print data
  source, dense accessible Project action/status surface, direct trilingual
  coverage and exact three-case visual evidence. The action remains visibly
  unavailable without an approved mapping and does not add a second primary
  action.
- Final exact product checkpoint
  `6ba2763cc14b3a044e2225d7a960ce02175f88a7` passed ordinary CI
  `31163598955`: repository `92819270517`, complete E2E/history secret scan
  and visual `92819270398`; controlled runtime correctly skipped.
- Final unchanged Gate `31164225729` passed repository `92821257912`, visual
  `92821257937` at `68/68` and controlled disposable Site `92821257859` with
  all diagnostic activation closed. Artifact `8988384460` records
  `result=PASS`, the exact SHA and `scope=p5-01-through-p5-06`; its GitHub
  digest is
  `sha256:6d77c9357dfd6c1fa354c93dd1a6773dfc20837246a9a37bc0edfd9cd4ee6bee`
  and extracted result digest is
  `aa84e488856c0eab31aa226a29169515de3097ef2655a544716a9eaf9b4155ff`.
- The serial P5-06 runtime repairs were effective rather than repeats. Each
  uniquely proved root advanced the same request to a later previously
  unreachable boundary, and earlier roots never recurred. The final two roots
  were verifier credential/probe defects after controlled-print creation had
  passed. No Requirement, API, permission, Schema intent, ownership,
  transaction, idempotency, audit, baseline, threshold or PASS rule changed.
- Release-gate review concludes `PASS — LEVEL 2 P5-06` and
  `PASS — LEVEL 3 PHASE 5`. `FR-PRN-001/002` are
  `TECHNICAL_VERIFIED`; `FR-PRN-003` remains decision-held by
  `DR-REC-003/004`. No production form, mapping, adapter, signer, copy policy,
  service, dependency, ERPNext endpoint or credential is active.
- Evidence is `implementation/evidence/phase-5/p5-06-validation.md`; the
  terminal decision is `implementation/phase-5-gate.md`. There is no active
  technical Hard Blocker.
- Standing transition authority activates only `P6-00 — Phase 6 Tooling
  requirement anchor`. It allocates `FR-TX-001..020`, preserves distinct
  Tooling identities and NPI/ERPNext ownership, routes the specialized
  workbook boundary through `xlsx-tooling-import`, retains
  `DR-REC-002/007/008/010`, and defines task/test/rollback sequencing without
  product code. P6-01/M5-01 remains inactive until that anchor passes.

## 2026-08-07 P6-00 requirement anchor PASS and P6-01 transition

- P6-00 completed the bounded repository/specification audit and froze the
  Phase 6 requirement, identity, ownership, task, test, migration and rollback
  boundary in `implementation/phase-6-requirement-anchor.md`.
- `FR-TX-001..020`, `FR-TL-001..018`, `UX-004`, `UX-007` and `UX-016` are
  allocated to P6-01 through P6-08. Anchored trace states mean allocation only;
  no Tooling requirement is relabelled implemented or accepted.
- Existing repository truth remains explicit: there is no live Tooling backend,
  metadata or BFF; the SPA Tooling page is an in-memory prototype; and the
  passive XLSX inspector is parser-safety foundation, not a runtime import.
- `DR-REC-002/007/008/010` remain scoped holds. No production lifecycle policy,
  exception-color semantics, workbook mapping, destructive rollback, adapter,
  ERPNext endpoint or credential was installed.
- P6-00 Level 2 documentation/trace checks pass: canonical 282-row trace,
  focused reconciliation `18/18`, YAML/source/evidence checks and
  `git diff --check`. Its entry checkpoint `ce401b8` passed exact-SHA ordinary
  CI `31165764919` with repository `92826073031`, complete E2E/history secret
  lanes and fixed-Linux visual `92826073108`; controlled runtime correctly
  skipped.
- Standing authority activates only the P6-01 Requirement/domain/existing-
  capability audit and task plan for Part/PartRevision, ToolingRequirement,
  ToolingMaster, versioned ToolingApplicability and the dense live cockpit.
  No product mutation is permitted until that plan freezes the exact
  no-lifecycle-command boundary.

## 2026-08-07 P6-01 requirement/domain audit PASS

- P6-00 exact checkpoint `6b5d034` passed ordinary CI `31167356140`:
  repository `92831145862`, complete E2E/current-tree/history secret lanes and
  fixed-Linux visual `92831145989` passed; controlled runtime correctly
  skipped.
- The P6-01 audit confirms no live Part, Part Revision, Tooling Requirement,
  Tooling Master or Tooling Applicability backend exists. The current Tooling
  SPA is an in-memory prototype and remains isolated from live product truth.
- `implementation/evidence/phase-6/p6-01-plan.md` freezes the minimum vertical
  slice, non-collapse/shared-master/effectivity invariants, fail-closed
  Project-first authorization, closed BFF, additive migration, staged test
  map and forward-only rollback.
- `DR-REC-010` continues to hold exact production lifecycle states,
  transitions and authorities. P6-01 introduces no lifecycle state or command,
  production policy/default, mapping, adapter, ERPNext endpoint or credential.
- Standing authority activates only checkpoint 1: pure domain, closed
  contract/ownership and six additive guarded DocTypes. A live route,
  repository, SPA and controlled Site remain inactive until their sequential
  checkpoints.

## 2026-08-07 P6-01 domain, contract and metadata checkpoint

- Product checkpoint `73c8a7a` adds the distinct Part/PartRevision,
  ToolingRequirement, ToolingMaster and immutable versioned/effective
  ToolingApplicability domain, six guarded additive DocTypes, closed schemas,
  exact ownership rows and direct English/`zh`/`zh-TW` coverage. It activates
  no route, live UI, business fixture, lifecycle, policy, default, adapter,
  ERPNext endpoint or credential.
- Local affected tests pass `21/21`; complete tracked Python passes
  `1,106/1,106`; i18n passes at `3,985` sources with direct `100%` `zh` and
  `100%` `zh-TW`; compilation, reconciliation, contract/metadata parsing,
  prototype/P0 governance and diff checks pass.
- Initial ordinary CI `31170493815` passed repository `92840992551` and all 50
  non-P0 visual cases. Its only failure was the exact eighteen P0 bottom-footer
  catalog fingerprints changing from `fd8d72a35779b6ea` to
  `05fc637e0c1286cb`. Artifact `8990825369`, digest
  `sha256:e9926ae4ab30a6e1b91ef3c1b02f7ecfa945a15decd41fe621a5fee20eca8ae2`,
  proves no workspace component, layout or state change.
- Baseline-only commit `62c063e` synchronizes those eighteen exact fixed-Linux
  actuals byte-for-byte. It changes no assertion, matrix, threshold or PASS
  rule and leaves every user Darwin image untouched.
- Final exact-SHA ordinary CI `31171293330` passes repository `92843457513`,
  complete E2E and both secret lanes, plus fixed-Linux visual `92843457422` at
  `68/68`; controlled runtime `92843458095` correctly skips. Visual artifact
  `8991126144` has digest
  `sha256:f163ed7b82018fe3ad807f3e90409a89214b5fd83d86f65b56e979cf422e9b81`.
- Checkpoint 1 is PASS, not P6-01 Level 2. Autopilot activates only the
  Project-first repository/BFF checkpoint with bounded queries, seven frozen
  narrow paths, actor-bound idempotency, transaction/audit, route switch and
  exact API/security tests. The live cockpit and controlled Site remain
  inactive until the sequential Gates pass.

## 2026-08-07 P6-01 authorized repository and closed BFF checkpoint

- Product checkpoint `96fdd84` adds Project-first authorized bounded cockpit
  and exact Master projections, the seven frozen BFF paths, same-tenant/
  current-revision/reference/effectivity validation, System Manager-only
  mutation, actor-bound sealed replay, one request transaction, append-only
  audit and an independent fail-closed route switch.
- Local affected tests pass `35/35`; complete Python passes `1,120/1,120`;
  i18n passes at `3,987` sources with direct `100%` `zh` and `100%` `zh-TW`;
  OpenAPI, configuration, reconciliation, governance and diff checks pass.
- Initial ordinary CI `31174458472` passed repository `92853267311`, complete
  E2E and both secret lanes plus all 50 non-P0 visuals. Its only failure was
  the exact eighteen P0 footer catalog fingerprints changing from
  `05fc637e0c1286cb` to `088d4637dea1703c`. Artifact `8992324656`, digest
  `sha256:e697467a89b314a6ed31ba2dc5275628c15de4d62a8362b7b17e4142cfa66691`,
  proves no workspace component, layout or state change.
- Baseline-only commit `4215bbe` synchronizes those eighteen exact fixed-Linux
  actuals byte-for-byte. It changes no assertion, matrix, threshold or PASS
  rule and leaves every user Darwin image untouched.
- Final exact-SHA ordinary CI `31175388717` passes repository `92856145644`,
  complete E2E and both secret lanes, plus fixed-Linux visual `92856145467` at
  `68/68`; controlled runtime `92856146245` correctly skips. Visual artifact
  `8992669663` has digest
  `sha256:6e0a0c711e8dd19f2962581f529faf2fcf1faa9c66bf06db01a6b4b54ade1831`.
- Checkpoint 2 is PASS, not P6-01 Level 2. Autopilot activates only the live
  dense Tooling cockpit/data-source checkpoint with capability-driven actions,
  honest downstream unavailable states, trilingual/accessibility/state and
  affected visual evidence. No controlled Site may run before its affected
  checks and complete ordinary CI pass.

## 2026-08-07 P6-01 live Tooling cockpit checkpoint

- Product checkpoint `a541cf9` adds the strict seven-route browser data source,
  Project-scoped cockpit/Master routes and dense tree/table/inspector. Create
  actions remain server-capability-driven and preserve CSRF, actor-bound
  idempotency and an exact-key/fresh-signal retry. Lifecycle, Tooling Revision,
  physical Set, Trial and ERPNext stay explicitly unavailable.
- Local affected frontend checks pass `64/64`; full frontend unit passes
  `730/730`; complete Python passes `1,120/1,120`; direct browser passes
  `13/13`; i18n passes `4,059` literal sources at direct `100%` `zh`/`zh-TW`;
  type, lint, generated, accessibility, P0/prototype/reconciliation, visual
  inspection, audit and diff checks pass.
- Initial ordinary CI `31180308383` isolated one stale inherited Shell
  expectation and `56` catalog-footer visual fingerprints. Artifact
  `8994577675`, digest
  `sha256:e517ad8161c0f591f945e8a75c6934e5ad1b3be7c91da565210198d342b8455f`,
  supplied exactly those stable Linux actuals.
- Repair checkpoint `2f3de3f` changes only that Shell assertion, synchronizes
  the `56` proved baselines and adds the five P6-01 visual cases to the
  governed matrix. Ordinary CI `31182336001` then passed repository and all
  `311` non-visual cases; its visual job passed the prior `68` and failed only
  the five newly governed cases without Linux baselines. Artifact `8995357252`,
  digest
  `sha256:f56e9f1e7eec67bf5c0e953670f736bb7a28251da3dedd2f2a7053e77c27591f`,
  contained exactly those five CRC-validated actuals.
- Final checkpoint `1f11f3c` adds only the five exact Linux baselines. Ordinary
  CI `31183116349` passes repository `92880986264`, `311/311` E2E, current-tree
  and history Gitleaks, and visual `92880986015` at `73/73`; controlled job
  `92880986862` correctly skips. Visual artifact `8995663993` has digest
  `sha256:aae122bfd243e5da75090182be806e14d052a36e2bb6083271cdc2d91ea7b89b`.
- Checkpoint 3 is PASS, not P6-01 Level 2. Autopilot activates only controlled
  disposable-Site migration/create/reuse/applicability/replay/rollback/IDOR/
  route-disable proof. Its verifier/workflow changes require affected checks
  and complete ordinary CI before dispatch. Exact lifecycle policy and every
  P6-02-through-P6-08 behavior remain inactive.

## 2026-08-07 P6-01 controlled runtime diagnostic

- Runtime-verifier checkpoint `42e2435` passed complete ordinary CI
  `31186227371`; repository `92891339039` and visual `92891338846` at `73/73`
  passed while controlled runtime correctly skipped.
- Controlled workflow `31186957232` retained that exact SHA. Repository
  `92893817844`, visual `92893817888`, pinned Bench, disposable Site,
  migrations and the cumulative P5 runtime passed. Controlled job
  `92893817778` then reached the first P6-01 `part.create`, which returned
  non-201; the diagnostics-closed verifier exposed no status-specific or
  substage root.
- Standing recovery authority activates one response-neutral Part-create
  diagnostic cycle: one allowlisted substage code, validated exception type
  and exact trace ID for only the first affected request; affected/full
  ordinary CI; at most one diagnostic Site; one repair only for the uniquely
  proved root; diagnostic closure; affected/full ordinary CI; and one final
  unchanged Gate. Counters are diagnostic `0/1`, repair `0/1`, final Gate
  `0/1`. This is `IN_PROGRESS_DIAGNOSTIC`, not a Hard Blocker.
- Diagnostic checkpoint `7bd0819` passed complete ordinary CI `31188466252`.
  The sole diagnostic Site `31189263393` returned only
  `P601_PART_CREATE_RECEIPT_INSERT / ValidationError /
  trace-fdeec6ebee38563791fb6f338ef1aa0e`. Pinned Frappe
  `Document.insert()` calls `_set_defaults()`, whose Select fallback uses the
  first option. The optional unsealed receipt target type had `part` as its
  first option, so validation correctly rejected the falsely target-bound
  pending receipt. This uniquely selects one metadata repair: prepend the
  empty Select option and close verifier diagnostic activation. Allowed sealed
  target values and every frozen product/Gate boundary remain unchanged.
- Receipt repair checkpoint `84ac63b` passed complete ordinary CI
  `31190599179`. Final unchanged workflow `31191425881` passed repository
  `92908918643`, visual `92908918453`, pinned Bench, Site, migrations and all
  predecessor runtime. Controlled job `92908918591` advanced beyond the former
  receipt-insert root and failed only when the first Applicability create did
  not return HTTP 201. The former repair is effective. Standing authority
  opens one new route-gated, response-neutral Applicability-create diagnostic
  cycle with counters diagnostic `0/1`, uniquely proved repair `0/1`, final
  unchanged Gate `0/1`; every frozen boundary remains unchanged.
- Applicability diagnostic checkpoint `f82906f` passed complete ordinary CI
  `31192675103`. The sole diagnostic Site `31193365348` returned only
  `P601_APPLICABILITY_CREATE_RELATIONSHIP_INSERT / ValidationError /
  trace-59e45d5266c05965a8e353f52abe26c5`; repository `92915506746` and visual
  `92915506767` passed. Pinned Frappe fills empty Selects from their first
  options. Both optional Product/Model source-system fields listed `NPI_ONE`
  first, so row validation correctly rejected those systems without paired
  object IDs. The unique repair prepends only empty options to those two
  optional Selects and closes verifier diagnostic activation.
- Optional-reference repair checkpoint `c1f627c` passed complete ordinary CI
  `31194339295`: repository `92918744817` and visual `92918744821` passed,
  while controlled runtime correctly skipped. Final unchanged workflow
  `31195049338` retained that SHA and diagnostics remained closed. Repository
  `92921107120`, visual `92921106655`, pinned Bench, Site, migrations and all
  predecessors passed; controlled job `92921106746` reached the same coarse
  relationship-insert stage after the former paired-reference root had been
  removed. The next unconditional contract check is deterministically
  contradictory: repository `_insert_applicability()` writes a raw version
  string, while the immutable DocType validator accepts only a namespaced
  SHA-256 digest. This uniquely proves
  `P601_APPLICABILITY_VERSION_KEY_HASH_MISMATCH`. Standing recovery authority
  activates only that formula-alignment repair, affected/full ordinary CI and
  one diagnostics-closed final unchanged Gate. It changes no Requirement,
  public API, permission, Schema intent, ownership, transaction, idempotency,
  audit or PASS rule.
- Initial repair `ab718e6` passed complete ordinary CI `31196125343` with
  repository `92924661787` and visual `92924661816`. Final unchanged Gate
  `31196918023` passed repository `92927290257`, visual `92927290466`, pinned
  Bench, Site, migrations and all predecessors; controlled job `92927290342`
  still returned the first Applicability command non-201. Direct re-audit of
  the full validator proves the repair transcribed only
  `relationship_global_id:version` and omitted the required leading
  `tenant_id:` namespace. Its test mirrored the incomplete helper and did not
  cross-check the validator. This is the same proved root and an incomplete
  technical repair, not a new product decision or Hard Blocker. Correct the
  exact `tenant_id:relationship_global_id:version` SHA-256 formula, add a
  cross-file contract assertion, run affected/full ordinary CI, then one
  diagnostics-closed unchanged Gate.

## 2026-08-07 P6-01 Level 2 PASS and P6-02 transition

- Corrective checkpoint `d0a9258` includes the exact tenant-namespaced
  Applicability version-key formula and a cross-file validator assertion.
  Complete ordinary CI `31197968661` passed repository `92930758119`, visual
  `92930757760` at `73/73`, both secret lanes and complete E2E; controlled job
  `92930758895` correctly skipped.
- Final diagnostics-closed workflow `31198574475` retained that exact SHA.
  Repository `92932746371`, visual `92932746394` and controlled runtime
  `92932746437` all passed. Runtime artifact `9001947238` has GitHub digest
  `sha256:4f4fa8d5884e71fc2b3388b23c45b55509f0482ad4e937fbbd7396a615130a65`.
- P6-01 passes its Level 2 Task Gate. `FR-TX-002` is technically verified;
  `FR-TX-001`, `UX-004`, `FR-TL-001` and `FR-TL-003` are technically verified
  foundations with their exact later dependencies retained.
- Standing automatic-transition authority activates only the P6-02 bounded
  Requirement/domain/existing-capability audit for `FR-TX-003` and
  `FR-TL-004`. It may plan distinct physical Set identity and customer-owned
  intake evidence, but may not invent lifecycle states/transitions/authorities
  held by `DR-REC-010`, claim ERPNext Asset success, or install production
  adapters, endpoints, credentials or defaults.

## 2026-08-07 P6-02 requirement/domain audit PASS

- P6-01 evidence checkpoint `49a8931` passed exact-SHA ordinary CI
  `31200277175`: repository `92938356572`, visual `92938356975`, complete E2E
  and both secret lanes passed; controlled job `92938357521` correctly
  skipped.
- The bounded P6-02 audit for `FR-TX-003` and `FR-TL-004` passes in
  `implementation/evidence/phase-6/p6-02-plan.md`. It freezes one immutable
  UUID per physical Set, no quantity collapse, customer ownership and custody/
  repair/return provenance, versioned intake snapshots, five exact inspection
  categories, independently identified differences and append-only URL-free
  references to exact clean private File Revisions.
- `DR-REC-010` continues to block exact Set lifecycle states/transitions/
  authorities. P6-03 owns exact source Tooling Revision, P6-04 owns formal
  Supplier projection, and ERPNext/P6-06/Phase 8 own Asset/state/location and
  external execution. Customer login/signature and file mutation are absent.
- Standing authority activates only P6-02 checkpoint 1: pure domain, closed
  contract, exact ownership rows, three guarded additive DocTypes and direct
  tests/i18n coverage. No repository route, live SPA behavior, business row,
  policy, adapter, endpoint, credential or external mutation may be activated.

## 2026-08-07 P6-02 domain, contract and metadata checkpoint

- Product checkpoint `e659d46` adds one immutable UUID per physical Set,
  customer ownership/custody provenance, immutable versioned intake/accessory/
  five-category inspection/difference truth, append-only URL-free exact clean
  private File Revision evidence, three guarded additive DocTypes, closed
  schemas, exact ownership rows and direct English/`zh`/`zh-TW` coverage. It
  activates no route, live UI, business fixture, lifecycle, policy, adapter,
  ERPNext endpoint, credential or external mutation.
- Local affected tests pass `30/30`; complete tracked Python passes
  `1,138/1,138`; frontend generation/type/lint/coverage/build passes; i18n
  passes at `4,127` sources with direct `100%` `zh` and `100%` `zh-TW`.
- Initial ordinary CI `31203653903` passed repository `92949376253` and all 55
  non-P0 visual cases. Its only failure was the exact eighteen P0 bottom-footer
  catalog fingerprints changing from `8d880a485a7ba1af` to
  `220fdc2cf42779bb`. Artifact `9003910006`, digest
  `sha256:4c31b017275e9a2ad24285671a39b05ba5961a7ae8de8c8b28c6649e26da3ea5`,
  proves no workspace component, layout or state change.
- Baseline-only commit `7b5dda1` synchronizes those eighteen exact fixed-Linux
  actuals byte-for-byte. It changes no assertion, matrix, threshold or PASS
  rule and leaves every user Darwin image and unrelated dirty file untouched.
- Final exact-SHA ordinary CI `31204720858` passes repository `92952842864`,
  complete E2E and both secret lanes, plus fixed-Linux visual `92952842802` at
  `73/73`; controlled runtime `92952843426` correctly skips. Visual artifact
  `9004313318` has digest
  `sha256:1cd53e5d0733ac13058d381c7afdaf0fe50d18133100cfd16ab8ae910d1dba6e`.
- Checkpoint 1 is PASS, not P6-02 Level 2. Automatic transition activates only
  checkpoint 2: Project-first bounded Set collection/detail queries and three
  narrow commands, exact Requirement/customer/File Revision containment,
  System Manager-only mutation, actor-bound idempotency, exact conflicts, one
  transaction, append-only audit, an independent fail-closed route switch and
  exact API/IDOR/rollback tests. The live SPA and controlled Site remain
  inactive until this checkpoint passes affected checks and complete ordinary
  CI. All scoped lifecycle/Revision/Supplier/ERP/customer/file holds remain.

## 2026-08-07 P6-02 repository and BFF checkpoint

- The preceding checkpoint-1 evidence commit `a78c91d` passed exact-SHA
  ordinary CI `31205863774`: repository `92956626704`, visual `92956626544`
  and controlled runtime `92956627373` correctly skipped.
- Product commit `c8f2ebc` adds Project-first bounded Set collection/detail
  projections and the three frozen narrow Set/intake/evidence commands. It
  enforces exact Requirement/customer/clean-private-File-Revision containment,
  System Manager-only mutation, actor-bound sealed replay, exact conflicts,
  one transaction, append-only audit and an independent fail-closed route
  switch. Its superseded run `31207891174` passed visual and repository
  verification before cancellation during E2E and is not classified PASS.
- Before any controlled Site, an exact source/metadata cross-check proved the
  reused command-receipt DocType Select/controller whitelist lacked all three
  P6-02 operation/target pairs. Correction `d339da5` adds only those exact
  values, administrator-visible `zh`/`zh-TW` translations and metadata tests;
  persisted/runtime contract values remain English. No Requirement, API,
  permission, Schema intent, ownership, transaction, idempotency, audit or
  PASS rule changed.
- Corrective ordinary CI `31208510139` passed repository `92965418919`,
  complete E2E and both secret lanes. Visual `92965418903` failed only the
  exact eighteen P0 footer fingerprints after catalog version changed from
  `220fdc2cf42779bb` to `957013df4ef08130`. Artifact `9005792248`, digest
  `sha256:8f02d8093e2b2306bf8d79890a21558515c5711fa197cc00e0d74f799c1bd5d6`,
  proves only `300/306` pixels per image and all significant deltas at
  `y=882..891`.
- Baseline-only checkpoint `39fe0e8` synchronizes the eighteen exact Linux
  actuals byte-for-byte and changes no component, state, assertion, matrix,
  threshold or PASS rule. Final ordinary CI `31209234574` passes repository
  `92967755668`, complete E2E, both secret lanes and visual `92967755547` at
  `73/73`; controlled runtime `92967756711` correctly skips. Visual artifact
  `9006061034` has digest
  `sha256:02a6db63a056cf03b4e5f3261c0a1d05ae7b16f49b7bf44d8c5d80fdee098991`;
  Gitleaks artifact `9006216901` has digest
  `sha256:7c2051e7809b5b17c8c0aa3691a3dec0513b1e52dffefbad50709091d7ed1397`.
- Checkpoint 2 is PASS, not P6-02 Level 2. Automatic transition activates only
  checkpoint 3: the strict server-backed Set/intake data source, dense live
  Tooling workspace, exact governed File Revision picker, honest unavailable
  states, capability-driven actions, complete three-language/accessibility
  coverage and affected visual matrix. Controlled Site remains inactive until
  checkpoint 3 passes affected checks and complete ordinary CI. All scoped
  lifecycle/Revision/Supplier/ERP/customer/file holds remain.

## 2026-08-07 P6-02 live workspace checkpoint

- Product commit `3b62046` adds only the strict server-backed Set/intake data
  source, dense Project/Master-scoped physical Set workspace, exact clean File
  Revision picker, operational states and direct trilingual/accessibility
  coverage already closed by checkpoint 2.
- Artifact-proved evidence commits `26685ff` and `b1df79f` add the P6-02 visual
  cases to the existing governed job and synchronize only the exact Linux
  actuals. They change no assertion, threshold or PASS criterion.
- Final ordinary CI `31215596601` passed repository `92988260703`, `315/315`
  non-visual E2E, both secret lanes and visual `92988260754` at `76/76`;
  controlled job `92988261221` correctly skipped.
- Checkpoint 3 is PASS, not P6-02 Level 2. Automatic transition activates only
  checkpoint 4: cumulative disposable-Site Set/intake/evidence/replay/
  rollback/IDOR/route-disable proof, complete ordinary CI and the Level 2 Task
  Gate. All lifecycle/Revision/Supplier/ERP/customer/file holds remain.

## 2026-08-07 P6-02 Level 2 PASS and P6-03 transition

- Runtime checkpoint `55db50e` passed complete ordinary CI `31218807211`.
  Its first diagnostics-closed Site `31219316958` passed every cumulative
  predecessor before the first customer-intake Requirement returned non-201.
  Exact repository/verifier review proved the fixture had advanced the Part to
  current Revision B but still referenced obsolete Revision A. Repair
  `8fe1730` changes only the two synthetic references and adds a current-
  Revision regression assertion; the product rule remains fail closed.
- The next ordinary CI `31219948750` passed product tests/build and failed only
  because the current npm advisory database newly classified transitive
  development package `nanoid <3.3.17` as high severity. Checkpoint `b80aae5`
  updates only the lock record from `3.3.16` to compatible `3.3.18`, adds no
  dependency and retains the zero-vulnerability gate.
- Final ordinary CI `31220440401` passed repository `93003610445`, `1,140`
  tracked Python tests, `738` frontend unit tests, `315` non-visual E2E, both
  Gitleaks lanes and visual `93003610420` at `76/76`; controlled job
  `93003611017` correctly skipped.
- The one final diagnostics-closed workflow `31221016483` retained exact SHA
  `b80aae5` and passed repository `93005400488`, visual `93005400579` and
  controlled runtime `93005400541`. Runtime artifact `9010425982` has digest
  `sha256:3b2ec3b719094e2835c8cb6161031dfcd99baba5e32c2deef3dec846cf3a050a`.
  It proves two independent physical Sets, two immutable intakes, two retained
  evidence references, sixteen audits, replay, rollback, IDOR and independent
  P6-01/P6-02 route disable/recovery under cumulative scope
  `p5-01-through-p6-02`.
- P6-02 passes Level 2 in
  `implementation/evidence/phase-6/p6-02-validation.md`. `FR-TL-004` is
  technically verified; `FR-TX-003` is a technically verified foundation with
  its exact later Revision/Supplier/lifecycle/ERP dependencies retained.
- Standing transition authority activates only the bounded P6-03
  Requirement/domain/existing-capability audit for `FR-TX-004..008`,
  `FR-TL-002`, `FR-TL-003` and `FR-TL-006`. Exact lifecycle
  states/transitions/authorities remain held by `DR-REC-010`; no formal
  Supplier, production Asset/location, workbook mapping, external execution,
  endpoint, credential or ERPNext success may be invented.

## 2026-08-07 P6-03 bounded audit and plan

- P6-02 Level 2 evidence checkpoint `36e2b9b` passed complete ordinary CI
  `31222318731`: repository `93009313398`, visual `93009313360`, and
  controlled runtime `93009313685` correctly skipped. Visual artifact
  `9010879069` has digest
  `sha256:61b68e9f5055cbe02161ece8511886d910c2356ea1c69d24513bcd275cd02bdc`;
  Gitleaks artifact `9010971627` has digest
  `sha256:6ee0736518ab9758ddfcbe6e8eef93850adb2fa445db1bbb6be2aa2f1811f333`.
- The bounded P6-03 Requirement/domain/existing-capability audit passes in
  `implementation/evidence/phase-6/p6-03-plan.md`. Repository truth has no
  Tooling Revision, cavity, insert, process chain or controlled Part
  specification record; existing cockpit and Set contracts correctly return
  `tooling_revision_not_delivered`.
- The plan freezes four additive append-only persistence records and a minimum
  complete vertical slice for immutable Tooling Revision/specification,
  cavity-to-Applicability mapping, inserts/changeovers, one-to-many external
  identities, controlled Part material/color/compliance truth, ordered
  primary/second-shot/overmold process chain and a one-time exact Set-source
  binding. The binding never rewrites a P6-02 Set snapshot.
- Standing transition authority activates only checkpoint 1: pure domain
  invariants, four guarded additive DocTypes, ownership, four closed receipt
  operation/target values, closed OpenAPI schemas and direct tests. No route,
  frontend command or controlled Site may activate in this checkpoint.
- `DR-REC-010` still holds exact lifecycle states, transitions and release
  authority. Formal Supplier, ERP Asset/location, combined Trial, automatic
  impact action, production workbook mapping, endpoint, credential and every
  external mutation remain unavailable.

## 2026-08-08 P6-03 domain, contract and metadata checkpoint

- Product checkpoint `35229fa` adds the frozen pure immutable Tooling
  Revision/specification/cavity/insert/external-identity/process-chain/Set-
  binding domain foundation, four guarded additive DocTypes, exact ownership
  rows, four closed receipt operation/target pairs, closed OpenAPI schemas and
  direct tests. It activates no repository, BFF route, frontend command or
  controlled Site.
- Its first ordinary CI failed only the eighteen durable P0 screenshots.
  Downloaded artifact review proved every pixel delta was confined to the
  translated catalog fingerprint in the bottom status bar. Isolated repair
  `96f201c` synchronized only the eighteen exact fixed-Linux baselines; no
  component, state, assertion, matrix, threshold or PASS rule changed.
- Final ordinary CI `31239993150` passes exact SHA `96f201c`: repository
  `93059251734` (`1,154` Python, `738` frontend unit, `315` non-visual E2E,
  `4,312` sources at complete direct `zh`/`zh-TW`, zero vulnerabilities and
  no leaks), visual `93059251780` at `76/76`; controlled job `93059252121`
  correctly skipped. Exact artifact IDs and digests are recorded in
  `implementation/evidence/phase-6/p6-03-domain-metadata-checkpoint.md`.
- Checkpoint 1 is PASS, not P6-03 Level 2. Standing transition authority now
  activates only checkpoint 2: Project-first bounded repository/BFF reads and
  narrow commands, exact containment/effectivity/current-tip checks, System
  Manager-only mutation, actor-bound idempotency, transaction, append-only
  audit, independent fail-closed route switch and exact API/IDOR tests.
- The live workspace and controlled Site remain inactive. `DR-REC-010` and
  every Supplier/ERP/Trial/impact/import/external-execution hold remain
  unchanged.

## 2026-08-08 P6-03 repository, BFF and API checkpoint

- Product checkpoint `8cc04a9` adds Project-first bounded Revision,
  controlled-Part-specification, process-chain and Set-binding reads/commands,
  exact containment/effectivity/current-tip checks, System Manager-only
  mutation, actor-bound sealed replay, one transaction, append-only audit,
  frozen closed BFF paths and an independent fail-closed P6-03 route switch.
- Ordinary CI `31242202985` passed repository `93064940926` and isolated only
  the eighteen durable P0 footer fingerprints. Artifact `9017410069` proved
  all eighteen business workspaces unchanged; repair `07ae986` synchronized
  only the exact reviewed fixed-Linux actuals without changing components,
  assertions, matrix, thresholds or PASS rules.
- Final ordinary CI `31242679688` passes exact SHA `07ae986`: repository
  `93066134884` (`1,170` Python, `738` frontend unit, `315` non-visual E2E,
  `4,316` sources at complete direct `zh`/`zh-TW`, zero vulnerabilities and no
  leaks), visual `93066134855` at `76/76`; controlled job `93066135083`
  correctly skipped. Exact artifact IDs/digests and changed-files evidence are
  recorded in
  `implementation/evidence/phase-6/p6-03-repository-api-checkpoint.md`.
- Checkpoint 2 is PASS, not P6-03 Level 2. Standing transition authority now
  activates only checkpoint 3: strict live data source, dense Project/Master-
  scoped Revision/specification/cavity/insert/process-chain workspace, exact
  initial Set-source binding, complete operational states, accessibility,
  direct trilingual coverage and affected visual tests.
- The controlled Site remains inactive. `DR-REC-010` and every Supplier/ERP/
  Trial/impact/import/external-execution hold remain unchanged.

## 2026-08-08 P6-03 live Revision workspace checkpoint

- Product checkpoint `ce68265` delivers the strict same-origin data source,
  dense Project/Master-scoped Revision/specification/cavity/insert/process-
  chain workspace and exact initial physical-Set source binding. Lifecycle,
  Supplier, ERP Asset/location, Trial, automatic impact and production import
  capabilities remain explicitly unavailable.
- Initial ordinary CI `31246274859` passed repository and isolated `25`
  inherited Tooling/catalog Linux deltas. Artifact `9018622549` proved the
  intended capability transition and footer fingerprint changes. Governance
  checkpoint `a50a39b` copies only those reviewed actuals and adds the P6-03
  spec/artifact paths to the governed visual job.
- Ordinary CI `31246925746` then passed every prior `76` visual and failed only
  the three newly governed P6-03 cases because their Linux baselines did not
  exist. Artifact `9018808318` supplied exactly the reviewed English,
  Simplified-Chinese and Traditional-Chinese actuals. Baseline checkpoint
  `c4e29a5` adds only those three images.
- Final ordinary CI `31247444413` passes exact SHA `c4e29a5`: repository
  `93078248192` (`1,165` Python, `744` frontend unit, `321` non-visual E2E,
  `4,419` direct trilingual sources, statements `80.07%`, zero vulnerabilities
  and no leaks), visual `93078248193` at `79/79`; controlled job `93078248620`
  correctly skipped. Exact artifact IDs/digests are recorded in
  `implementation/evidence/phase-6/p6-03-live-workspace-checkpoint.md`.
- Checkpoint 3 is PASS, not P6-03 Level 2. Standing transition authority now
  activates only checkpoint 4: cumulative disposable-Site migration and
  immutable Revision/specification/cavity/insert/external-identity/process-
  chain/Set-binding persistence, replay, conflict, rollback, IDOR and
  independent P6-03 route-disable/recovery proof. Complete ordinary CI must
  pass before controlled dispatch.
- `DR-REC-010` and every Supplier/ERP/Trial/impact/import/external-execution
  hold remain unchanged. Production ERPNext must not be contacted.

## 2026-08-08 P6-03 Level 2 PASS and P6-04 transition

- Runtime checkpoint `a0c0802` and its serial verifier repairs established the
  exact P6-03 cumulative disposable-Site boundary. One generic and one closed
  revision-create response-neutral diagnostic narrowed the opaque database
  failure to `P603_REVISION_INSERT / OperationalError` without exposing input
  or changing the public response.
- Repair `05a27b8` converts all four P6-03 audit timestamps through the
  existing validated Frappe UTC DateTime boundary. Controlled run
  `31253676998` then passed fresh P6-03 persistence and isolated only the
  inherited P6-01 recovery probe's pre-P6-03 count expectation. Repair
  `ff32f0b` asserts the exact cumulative totals and does not weaken them to an
  inequality.
- Complete ordinary CI `31253903494` and controlled workflow `31253914746`
  proved every repair and the complete cumulative path. Because the temporary
  P6-03 diagnostic request header was still enabled, that controlled PASS is
  retained as repair evidence rather than accepted as the final Task Gate.
- Checkpoint `4ab4782` closes P6-03 diagnostic activation. Final ordinary CI
  `31254281586` passes repository `93095213074` (`1,177` Python, `744`
  frontend unit, `321` non-visual E2E, statements `80.07%`, `4,419` direct
  trilingual sources, zero vulnerabilities and no leaks), visual
  `93095213086` at `79/79`; controlled job `93095213506` correctly skipped.
- Final unchanged workflow `31254642262` retains exact SHA `4ab4782` and
  passes repository `93096129318`, visual `93096129329` at `79/79` and
  controlled runtime `93096129310`. Artifact `9021059611`, digest
  `sha256:aa0b3c80f38ae7ac6acbe16245e5baf6e176c470c15bf7a435dae231afee52bc`,
  records `p5-01-through-p6-03`; diagnostics are closed.
- P6-03 passes Level 2 in
  `implementation/evidence/phase-6/p6-03-validation.md`. Exact cavity/Part,
  insert, external-identity, controlled Part specification, immutable Tooling
  Revision/process-chain and initial Set-source binding truth is live. Trial,
  automatic impact and lifecycle approval/release dependencies remain
  explicit foundations rather than false completion claims.
- Standing transition authority activates only the bounded P6-04 Requirement/
  domain/existing-capability audit for `FR-TL-005..008`. It must separate
  internal make/buy, Supplier/milestone and design-release dependency from
  ERPNext-owned PO/receipt/invoice/actual-cost truth. No supplier portal,
  production lifecycle rule, ERP mutation, endpoint, credential or successful
  target result may be invented.
