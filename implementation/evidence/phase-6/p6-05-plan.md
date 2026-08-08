# P6-05 Plan — Defects, Process Truth and Capacity Scenarios

Recorded: `2026-08-08T16:55:00Z`

Starting product checkpoint:
`5ca13abdbbbe08493ee54e9627849cfb0afdec01`

Starting synchronized controller checkpoint:
`e38da24bc75eeadd5bdb6f1f2f0b6d34b42d45ae`

Starting exact-SHA ordinary CI:
`31267848021` (`PASS`; repository `93128792398`, fixed-Linux visual
`93128792366` at `82/82`, controlled runtime `93128792624` correctly skipped)

Status:
**PASS — BOUNDED REQUIREMENT/DOMAIN AUDIT; DOMAIN/CONTRACT/METADATA FOUNDATION NEXT**

Requirements:

- `FR-TX-009`;
- `FR-TX-010`;
- `FR-TX-011`;
- `FR-TX-019`;
- `FR-TX-020`;
- `FR-TL-009`;
- `FR-TL-010` foundation;
- `FR-TL-017` foundation; and
- `FR-TL-018` foundation.

Applicable Skills:

- `repo-discovery`;
- `npi-domain-guard`;
- `frappe-safe-change`;
- `industrial-ux`; and
- `frappe-i18n`.

## 1. Sources and existing-capability conclusion

The audit used the Phase 6 requirement anchor, M5-05 backlog allocation,
current trace rows, matching DOCX/Pack requirements, `DOMAIN_MODEL.md`,
`TOOLING_AND_TRIAL.md`, the accepted reconciliation addendum and Decision
Requests, the complete ownership and OpenAPI contracts, P6-01 through P6-04
Level 2 evidence, the Project Work/Gate implementations, the current Tooling
domain/repositories and the deterministic Tooling and Trial prototypes.

Repository truth is:

- P6-01 through P6-04 provide distinct Project/Part/Requirement/Master/
  Applicability/Revision/Set identities, exact cavity and Part mappings,
  controlled process/specification values, immutable manufacturing plans and
  exact internal observations. They provide no Tooling defect, process-value
  layer, capacity-scenario or health-score persistence;
- the shared Project Work domain has policy-bound `issue` and `action` work
  items with `low/medium/high/critical` severity and an explicit `blocking`
  flag. It does not store cavity, root-cause, containment, target-Trial or
  verification truth and has no work-item transition command. It is therefore
  reusable presentation/authority context, not a Tooling-defect aggregate;
- Gate Review can consume exact current same-Gate blocking Work Items. There
  is no approved mapping from a Tooling-defect severity to a Gate Work Item,
  no Phase 7 Trial context and no authority to mutate G5/G6 from this task;
- `frontend/src/pages/tooling-page.tsx` and `trial-page.tsx` contain
  deterministic defect, parameter and status examples. They are in-memory UX
  reference only and cannot be relabelled as live facts;
- no `Trial`/`TrialRound` repository exists. A caller-supplied T0/T1 label,
  actual value or approval flag cannot prove a measured Trial Actual or an
  Approved Process Baseline;
- Tooling Revision already retains target cycle, capacity and machine
  specification facts. Those engineering specification values are not Trial
  Actuals and do not become an Approved Process Baseline;
- NPI One owns Tooling development defects, process-value provenance and
  capacity scenarios. ERPNext owns formal quality results, asset status,
  physical location, shot count, maintenance and actual operating history;
- no production IoT/ERP reader, calibration policy, health-score formula or
  preventive-maintenance policy is present; and
- `DR-REC-002` blocks only final production exception-color semantics.
  `DR-REC-010` continues to block Requirement/Revision/Set lifecycle commands,
  but does not block a separate, explicitly specified Tooling-defect workflow,
  immutable process facts or capacity scenarios.

The safe path is additive and needs no architecture ADR. It must expose every
missing Trial, ERP/IoT, maintenance or policy dependency as unavailable and
must never copy a standard into the actual or approved-baseline layer.

## 2. Scope and truthful completion boundary

P6-05 delivers this minimum vertical slice:

> open an authorized Project and Tooling Master -> select one exact immutable
> Tooling Revision and optional exact cavity -> create and append controlled
> Tooling-defect revisions with explicit severity, blocking intent,
> responsibility, containment/corrective actions and clean verification
> evidence -> inspect immutable defect/action history and open-blocker truth ->
> append a versioned Customer Standard process profile without inventing a
> Trial Actual or Approved Baseline -> compare the exact three fact slots and
> receive `not_measured`/`unavailable` until a later exact Trial supplies them
> -> append and revise an explicit multi-Part Capacity Scenario -> inspect
> deterministic part/day/month, assembly capacity, bottleneck and gap results
> with every business input and calculation rule visible

The slice separates five independent facts:

1. an NPI-owned Tooling defect and its immutable revision history;
2. NPI-owned containment/corrective/preventive action snapshots and exact
   verification evidence;
3. Customer Standard/Provided Specification values;
4. future Phase 7 Trial Actual and Approved Process Baseline values, which
   remain unavailable in the live P6-05 command path; and
5. a planning Capacity Scenario whose inputs and calculated outputs are both
   immutable and versioned, not fields on Tooling Master.

The workspace may show an explicit Tooling-defect `blocking` flag and open
blocking count, but it does not silently create a Project Work Item or mutate
a Gate. Phase 7 must connect an exact approved Trial/quality/Gate policy before
claiming final G5/G6 enforcement. Severity never implicitly sets blocking.

Expected evidence-driven trace truth is:

- `FR-TL-009`: technically verified foundation for exact defect, action,
  responsibility, target-round intention and verification truth; final
  Trial/G5/G6 policy integration remains Phase 7;
- `FR-TL-010`: technically verified foundation for exact future Trial context,
  comparison slots and target-round references; Trial rounds and comparisons
  remain Phase 7;
- `FR-TL-017`: technically verified foundation through a closed explicit
  unavailable ERP/IoT shot-count and calibration projection; no count is
  fabricated;
- `FR-TL-018`: technically verified foundation through a closed explicit
  unavailable health-score/maintenance-policy projection; no score or advice
  is fabricated;
- `FR-TX-009` and `FR-TX-019`: technically verified foundation for immutable
  separated process layers and live Customer Standard values; actual and
  approved-baseline creation remain Phase 7;
- `FR-TX-020`: technically verified foundation for exact rule-versioned
  comparison and all four textual states; production color semantics remain
  held by `DR-REC-002`; and
- `FR-TX-010..011`: technically verified for complete versioned Capacity
  Scenario inputs, deterministic formula, outputs, recomputation, bottleneck
  and gap without hidden business constants.

## 3. Non-scope and scoped holds

P6-05 does not install or infer:

- a Trial/TrialRound identity, T0/T1 numbering authority, Trial input lock,
  run/submission/approval, actual measurement or Trial comparison completion;
- an Approved Process Baseline without exact future approved Trial evidence;
- a Tooling Requirement/Revision/Set lifecycle state or transition,
  manufacturing authority, acceptance state or release command
  (`DR-REC-010`);
- a severity-to-`blocking` rule, automatic Domain Work Item, automatic Gate
  blocker, G5/G6 mutation, project-health mutation or production escalation;
- red/error coloring for any nonzero or outside-tolerance variance
  (`DR-REC-002`). The state remains visible through text and icon/shape;
- an inferred tolerance, unit conversion, default OEE/yield/cycle/hours/days/
  usage/set count/demand, hidden 22-hour/26-day constant or imported `#REF!`
  result;
- an assertion that scenario-effective Sets are operational production assets.
  Selected exact Tooling Sets and the explicit count remain scenario
  assumptions while Tooling lifecycle/ERP asset truth is unavailable;
- an ERPNext Quality Inspection/NCR write, formal quality result, Asset,
  location, shot-count, maintenance, repair, downtime or production result;
- a production ERP/IoT endpoint, credential, adapter, Webhook, background job,
  replay, reconciliation or target-confirmed observation;
- a health-score formula, lifetime threshold, calibration rule, predictive
  maintenance recommendation or production warning; or
- P6-06 acceptance, P6-07 import, P6-08 export or any Phase 7 behavior.

No business fixture, default tolerance, default capacity assumption, policy,
mapping, adapter, credential or external mutation is installed by migration.

## 4. Frozen domain design

### 4.1 Tooling defect revision aggregate

`ToolingDefectRevision` is an append-only NPI-owned aggregate snapshot. It
contains:

- stable `defectGlobalId`, immutable revision `globalId`, `defectVersion`,
  direct predecessor identity/hash and exact Project/Master/Tooling Revision
  scope;
- optional exact cavity UUID/identifier resolved from that Tooling Revision;
- bounded business code/title/description, a closed category key, shared
  `low/medium/high/critical` severity, and an explicit independent `blocking`
  boolean. Severity never changes the blocking flag implicitly;
- detection context as a closed union. P6-05 activates only exact Tooling
  Revision, manufacturing-plan/milestone observation, Set-intake/difference
  and `unavailable_trial_context` branches. Phase 7 owns the exact Trial branch;
- root-cause state (`pending` or `recorded`) plus bounded causal text only when
  recorded, one responsible Project-member snapshot and an optional external
  responsibility label clearly marked as unverified planning data;
- an ordered, UUID-addressed action snapshot. Each action has type
  `containment`, `corrective` or `preventive`, bounded detail, exact responsible
  Project member, due date, explicit `planned`/`completed`/`verified` state and
  zero or more clean private File Revision evidence snapshots;
- target-round intention as a bounded business label only, separately exposing
  `trialReference: unavailable` until Phase 7. A T1-like label is never used as
  a Trial identity;
- exact clean private File Revision detection/analysis/verification evidence;
  raw private URLs are never returned; and
- a closed defect state, actor, reason, request/trace and snapshot hash.

The Pack status sequence is implemented only for this Tooling-defect aggregate:

`open -> assigned -> in_progress -> ready_for_verification -> closed`, with
`closed -> reopened -> assigned`. No skip, deletion or direct close exists.
Creating a successor revision requires the immediate predecessor and its hash.
Moving to `ready_for_verification` requires at least one corrective action;
moving to `closed` requires all actions completed or verified plus exact clean
verification evidence; reopening requires a reason and preserves prior
verification. These states do not authorize Tooling lifecycle transitions.

### 4.2 Separated process-value profile revisions

`ToolingProcessProfileRevision` is an immutable versioned set of typed metrics
under exactly one fact layer:

- `customer_standard` / Provided Specification;
- `trial_actual`; or
- `approved_baseline`.

Every profile retains stable profile identity, version/predecessor/hash,
Project/Master/Tooling Revision, exact context/source identity and hash,
effectivity, actor and an ordered set of unique metric codes. Initial closed
metric codes cover `cycle_time`, `part_weight`, `runner_weight`,
`gross_weight_per_cavity`, `machine_tonnage` and `machine_type`. Numeric values
carry canonical decimal plus explicit unit; text values carry a bounded exact
value and no numeric delta.

P6-05 exposes a command only for `customer_standard`. Its source must be one
exact current released controlled Document Revision or an exact immutable
Tooling Revision specification snapshot. The pure domain and closed response
schemas support the other layers, but the production repository returns:

- `trial_actual: not_measured` with `trial_context_unavailable`; and
- `approved_baseline: unavailable` with
  `approved_trial_evidence_unavailable`.

There is no caller flag that can turn either slot into an available value.
Phase 7 must add exact Trial/approval readers and separate commands before
those layers can be persisted.

### 4.3 Versioned comparison rules and states

A numeric Customer Standard metric may include one exact
`ProcessComparisonRuleSnapshot` with stable rule identity, version/hash, unit
and inclusive absolute lower/upper bounds. No tolerance is inferred when the
rule is absent. The deterministic comparison returns:

- `not_measured` when the exact Trial Actual is absent;
- `unavailable` when the comparable target/rule/unit is absent or mismatched;
- `within_tolerance` when the actual falls inside the exact inclusive bounds;
  or
- `outside_tolerance` otherwise.

Numeric delta and percent delta are produced only from comparable exact values;
percent delta is unavailable when the comparison target is zero. The response
retains rule identity/version/hash and source profile hashes. It never includes
a caller-supplied status. `DR-REC-002` keeps the production visual tone
unavailable; the workspace uses literal state text plus non-color-only icons
and neutral industrial emphasis.

### 4.4 Versioned Capacity Scenario

`ToolingCapacityScenarioRevision` is append-only with stable scenario identity,
version/predecessor/hash, Project scope, title/effectivity, target monthly
assembly demand, explicit formula version and one or more unique exact Part/
Applicability capacity lines.

Every line freezes:

- exact Part Revision and Tooling Applicability identity/hash;
- explicit available hours per day, working days per month, OEE ratio, yield
  ratio, cycle seconds, cavity count, usage per assembly and effective-set
  count;
- optional exact selected Tooling Set identities. Their count must equal the
  explicit effective-set assumption when supplied, and every Set must belong
  to the Master; the scenario never calls them operational Assets; and
- the exact provenance kind/hash for cycle, cavity, usage and set assumptions.

Formula `capacity.v1` is contract-visible:

```text
parts_per_day = available_hours_per_day * 3600 / cycle_seconds
                * oee_ratio * yield_ratio * cavity_count
                * effective_set_count
parts_per_month = parts_per_day * working_days_per_month
assembly_units_per_day = parts_per_day / usage_per_assembly
assembly_units_per_month = parts_per_month / usage_per_assembly
scenario_assembly_units_per_month = minimum(line assembly_units_per_month)
gap = maximum(target_monthly_assembly_units
              - scenario_assembly_units_per_month, 0)
```

`3600` is the published hours-to-seconds unit conversion, not a business
assumption. Calculation uses decimal arithmetic and a contract-visible
`decimal-6-half-even` output rule; raw inputs and unrounded intermediate
canonical strings remain in the immutable snapshot. The deterministic
bottleneck is every line tied at the minimum, ordered by stable line UUID.
Changing a set count, cycle, OEE, yield or any other input appends a complete
successor scenario; earlier results are never overwritten.

### 4.5 ERP/IoT shot-count and health projection

`ToolingHealthProjection` is a closed read-only capability:

- the production default is `unavailable` and separately identifies missing
  target-confirmed shot-count/maintenance observations, source/calibration
  policy and health-score policy; and
- any future injected available branch must retain ERP/IoT source identity,
  target version, observation time, manual/automatic source, calibration
  version and exact maintenance/downtime inputs before a versioned scoring
  rule may calculate a score or recommendation.

P6-05 implements only the unavailable production branch and strict pure
parsing tests. It displays no zero count, score, warning or preventive action.

## 5. Planned additive BFF contract

The closed BFF adds only:

| Path | Purpose |
|---|---|
| `GET /projects/{projectId}/tooling/{toolingMasterId}/engineering-controls` | read bounded defect revisions, process-layer/comparison truth, capacity scenarios and explicit health/Trial capabilities |
| `POST /projects/{projectId}/tooling/{toolingMasterId}/defect-revisions` | create an initial or immediate-successor Tooling-defect revision |
| `POST /projects/{projectId}/tooling/{toolingMasterId}/process-profile-revisions` | append only a Customer Standard/Provided Specification profile revision |
| `POST /projects/{projectId}/tooling/{toolingMasterId}/capacity-scenario-revisions` | create an initial or immediate-successor Capacity Scenario with deterministic outputs |

Unsafe commands require authenticated session, CSRF, UUID request ID,
actor-bound idempotency and exact optimistic/predecessor/source/evidence
preconditions. Every write re-resolves Project membership, exact Master/
Revision/Applicability/Part/Cavity/Set and clean File/controlled-document
dependencies. System Manager is management transport only and does not become
defect verifier, Trial approver, Tooling authority or Gate authority.

There is no Trial Actual, Approved Baseline, Gate, ERP/IoT, health-score or
Tooling lifecycle write route. An independent P6-05 fail-closed route switch
covers only these four routes and projections.

## 6. Persistence and ownership plan

Checkpoint 1 adds only three guarded DocTypes:

- `NPI Tooling Defect Revision`;
- `NPI Tooling Process Profile Revision`; and
- `NPI Tooling Capacity Scenario Revision`.

Action, evidence, process metric/rule and capacity input/result structures are
bounded canonical immutable snapshots with independent UUIDs and exact hashes.
Generic Desk create/update/delete, export, print, share, raw private URLs and
arbitrary JSON mutation remain denied.

The existing `NPI Tooling Command Idempotency` and append-only audit mechanism
are reused with exactly three new operation/target pairs:

- `tooling_defect.revise`;
- `tooling_process_profile.create`; and
- `tooling_capacity_scenario.create`.

Ownership rows record NPI ownership of defect/process/capacity snapshots,
future Phase 7 ownership of Trial Actual and approved-baseline creation, and
ERPNext/Future Adapter ownership of formal quality, shot-count, maintenance and
health-source observations. Migration is additive and idempotent and creates
no domain row, result, default, policy, mapping or adapter.

## 7. Live workspace and i18n plan

- The selected-Master live Tooling surface gains a dense engineering-controls
  workspace adjacent to manufacturing, reusing the established tree/table/
  inspector shell and never activating prototype values.
- Defect rows expose state, severity, explicit blocking, exact location,
  responsibility, action completion, target-round intention, evidence and
  immutable lineage. State and blocking are expressed with text/icon/shape;
  color is auxiliary.
- Process comparison presents Customer Standard, Trial Actual and Approved
  Baseline as three fixed columns. Missing actual remains `not_measured`,
  missing approved evidence remains `unavailable`, and no copy/approve action
  is shown.
- Capacity inputs and calculated outputs are presented together with formula
  version, source assumptions, exact Set/Part references, bottleneck and gap.
  One edit produces a new scenario revision; it never overwrites a result.
- Shot count, health score and maintenance stay in a separate labelled
  ERP/IoT capability section with exact unavailable reasons.
- One context has at most one primary action. Trial submission, baseline
  approval, Gate mutation, Tooling lifecycle, ERP/IoT and maintenance actions
  are absent or explicitly unavailable.
- Normal, empty, loading, no-permission, read-only, unavailable,
  `not_measured`, validation, conflict, processing and retry states are
  explicit. Keyboard, focus, labels and non-color-only state are mandatory.
- Every visible source string is literal English through `t()` with complete
  direct `zh` and `zh-TW` coverage. Business values/codes/units use only the
  existing allowlist boundary.

## 8. Planned checkpoints

1. **Domain/contract/metadata foundation** — pure immutable defect/action/
   evidence, process-layer/comparison, capacity formula/scenario and explicit
   unavailable health domains; three guarded additive DocTypes; ownership,
   receipt values and closed OpenAPI schemas; no active route.
2. **Repository/BFF checkpoint** — Project-first bounded read and three narrow
   append commands, exact dependency containment, transaction/idempotency/
   audit, unavailable Trial/health readers, independent route switch and
   API/IDOR/no-fake-actual/no-ERP-write tests.
3. **Live workspace checkpoint** — strict data source, dense defect/process/
   capacity/health surface, complete trilingual/accessibility/state and
   affected visual tests; deterministic prototypes remain isolated.
4. **Controlled runtime and Task Gate** — disposable-Site defect succession/
   actions/evidence/blocking, Customer Standard separation with absent actual/
   baseline, capacity successor recomputation/bottleneck/gap, replay/conflict/
   rollback/IDOR and route-disable proof, complete ordinary CI and P6-05
   Level 2.

Complete ordinary CI is mandatory before a controlled-Site boundary.
Diagnostics stay closed unless an opaque exact-SHA failure activates one
governed response-neutral diagnostic cycle under standing authority.

## 9. Requirement to code to test to evidence

| Requirement | Planned delivery | Required evidence |
|---|---|---|
| `FR-TL-009` | immutable Tooling-defect revisions, exact location/severity/blocking, responsibility, root cause, action and verification evidence; no automatic Gate mutation | succession/transition/action/evidence/member/cavity/replay/IDOR tests, open-blocker UI/runtime and truthful Phase 7 hold |
| `FR-TL-010` | target-round intention and closed unavailable exact Trial context; three process slots ready for future Trial reader | no-label-as-identity, no caller actual/approval, `not_measured`/unavailable UI/runtime and foundation status |
| `FR-TL-017` | explicit unavailable ERP/IoT shot-count/source/calibration projection | no zero/default/count write, strict unavailable contract/UI/runtime and Phase 8 dependency |
| `FR-TL-018` | explicit unavailable health/maintenance-policy projection | no score/advice/default, strict unavailable contract/UI/runtime and Phase 8 dependency |
| `FR-TX-009`, `FR-TX-019` | immutable layer-specific process profiles with unit/source/context/effectivity and no Standard-to-Actual copy | layer/context/hash/unit tests, Customer Standard live path, actual/baseline unavailable and Phase 7 hold |
| `FR-TX-020` | exact versioned inclusive-bound rule, delta/percent and four textual states without production red semantics | boundary/zero/unit/missing/rule/hash tests, neutral non-color UI and `DR-REC-002` retained |
| `FR-TX-010`, `FR-TX-011` | explicit immutable multi-line Capacity Scenario and `capacity.v1` calculation with part/day/month, assembly units, bottleneck and gap | no-default/formula/precision/tie/recompute/predecessor/set/applicability tests, UI and controlled runtime |

Final evidence will be recorded in
`implementation/evidence/phase-6/p6-05-validation.md`.

## 10. Changed-files to affected-tests

| Expected change surface | Minimum direct checks |
|---|---|
| P6-05 pure domain | defect succession/state/action/evidence, process-layer non-collapse and comparison, capacity formula/version/recompute, unavailable health |
| three additive DocTypes and guards | exact parent/tenant containment, immutable snapshots, denied generic CRUD/delete, receipt values and additive/idempotent migration |
| OpenAPI and ownership | parse/reference/closed schemas, no caller actual/approval/status/result, exact unavailable unions and field ownership |
| Tooling repository/API/security | Project-first authorization, exact dependencies, replay/conflict/audit/rollback/IDOR, independent switch and no ERP/Gate/Trial mutation |
| Tooling data source/live workspace | strict parser, all operational states, accessibility, no prototype leakage and read-only unavailable truth |
| catalogs/styles | literal English plus direct `zh`/`zh-TW`, terminology/mixed-language, industrial boundary and affected visual matrix |
| runtime verifier/workflow | defect successor/evidence, separated process slots, capacity successors, replay/rollback/IDOR and route disable/recovery |
| controller/evidence | YAML, V1.2 reconciliation, Task Diff Review and `git diff --check` |

## 11. Migration, rollback and exit

Before retained P6-05 rows exist, a disposable environment may restore the
starting product checkpoint and migrate fresh. After retained history exists,
rollback disables only P6-05 routes/projections, preserves every defect,
action/evidence, process profile, comparison source, capacity scenario, audit
and idempotency receipt, and deploys a reviewed forward fix. It never rewrites
P6-01 through P6-04 identities/history, a controlled Document, a Gate/Work
Item, Trial/quality object or an ERPNext object.

The audit passes. Autopilot may start only checkpoint 1: pure domain, closed
contract and additive metadata foundation. Repository routes, live SPA,
controlled-Site execution and every Trial/Gate/ERP/IoT behavior remain inactive
until their preceding checkpoints pass. P6-06 and later remain inactive.
